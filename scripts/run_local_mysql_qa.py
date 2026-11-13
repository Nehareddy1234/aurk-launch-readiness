"""Create and remove a disposable localhost MySQL schema for critical QA checks."""
import os
from pathlib import Path
import secrets
import subprocess
import sys
from dotenv import dotenv_values
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from scripts.run_qa import redact


def main():
    values = dotenv_values('.env')
    url = make_url(values['DATABASE_URL'])
    if url.get_backend_name() != 'mysql' or url.host not in {'localhost', '127.0.0.1', '::1'}:
        raise SystemExit('Refusing a non-local MySQL connection.')
    schema = 'aurk_qa_local_' + secrets.token_hex(6)
    assert schema.startswith('aurk_qa_local_') and all(c.isalnum() or c == '_' for c in schema)
    engine = create_engine(url, isolation_level='AUTOCOMMIT')
    created = False
    try:
        with engine.connect() as connection:
            connection.exec_driver_sql(f'CREATE DATABASE `{schema}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci')
        created = True
        environment = os.environ.copy()
        environment.update(TEST_DATABASE_URL=url.set(database=schema).render_as_string(hide_password=False),
                           CUSTOMER_EMAILS_ENABLED='false', MAIL_SERVER='', WHATSAPP_ACCESS_TOKEN='')
        selected = sys.argv[1:] or [
            'tests/integration/test_qa_commerce.py::test_mysql_last_unit_concurrency',
            'tests/integration/test_qa_commerce.py::test_mysql_overlapping_workers_send_once',
            'tests/integration/test_qa_email_edges.py::test_new_email_is_due_even_with_second_precision_mysql',
            'tests/integration/test_qa_database.py', 'tests/integration/test_migrations.py']
        Path('qa_artifacts').mkdir(exist_ok=True)
        command = [sys.executable, '-m', 'pytest', *selected, '-q', '-p', 'no:cacheprovider',
                   '--randomly-seed=20261028', '--tb=short', '--junitxml=qa_artifacts/mysql-local.xml']
        process = subprocess.Popen(command, env=environment, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                   text=True, encoding='utf-8', errors='replace')
        with Path('qa_artifacts/mysql-local.log').open('w', encoding='utf-8') as log:
            for line in process.stdout:
                safe = redact(line)
                log.write(safe)
                log.flush()
                print(safe, end='', flush=True)
        process.wait()
        xml = Path('qa_artifacts/mysql-local.xml')
        if xml.exists():
            xml.write_text(redact(xml.read_text(encoding='utf-8')), encoding='utf-8')
        return process.returncode
    finally:
        if created:
            with engine.connect() as connection:
                connection.exec_driver_sql(f'DROP DATABASE `{schema}`')
            print('Disposable MySQL QA schema removed. Store database was not modified.')
        engine.dispose()


if __name__ == '__main__':
    raise SystemExit(main())
