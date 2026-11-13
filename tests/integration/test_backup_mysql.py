"""Synthetic SQL/uploads round trip; never runs against a non-QA database."""
import json
import os
from pathlib import Path
import subprocess

import pytest
from app.extensions import db
from app.models import Product
from scripts.backup_archive import pack_backup, extract_backup


def test_mysql_backup_and_restore_synthetic_store(app, qa_factory, tmp_path):
    with app.app_context():
        url = db.engine.url
        if url.get_backend_name() != 'mysql':
            pytest.skip('Requires disposable local MySQL and client tools')
        assert url.host in {'localhost', '127.0.0.1', '::1'}
        assert url.database and any(word in url.database.lower() for word in ('qa', 'test'))
    client_dir = os.environ.get('QA_MYSQL_CLIENT_DIR')
    if not client_dir:
        pytest.skip('Set QA_MYSQL_CLIENT_DIR to the isolated MySQL client directory')
    extension = '.exe' if os.name == 'nt' else ''
    product = qa_factory.product(name='QA restore sentinel')
    uploads = tmp_path / 'uploads'
    uploads.mkdir(exist_ok=True)
    (uploads / 'sentinel.txt').write_text('Synthetic upload only', encoding='utf-8')
    defaults = tmp_path / 'client.cnf'
    # Disposable credentials go to a short-lived file, never the command line.
    def quoted(value):
        return '"' + str(value).replace('\\', '\\\\').replace('"', '\\"') + '"'
    defaults.write_text('[client]\n' + '\n'.join(f'{key}={quoted(value)}' for key, value in {
        'host': url.host, 'port': url.port or 3306, 'user': url.username,
        'password': url.password, 'protocol': 'TCP',
    }.items()) + '\n', encoding='utf-8')
    defaults.chmod(0o600)
    dump = tmp_path / 'database.sql'
    try:
        with dump.open('wb') as output:
            subprocess.run([str(Path(client_dir) / ('mysqldump' + extension)),
                f'--defaults-extra-file={defaults}', '--single-transaction', '--no-tablespaces',
                '--set-gtid-purged=OFF', url.database], stdout=output, stderr=subprocess.PIPE,
                check=True, timeout=60)
        bundle = tmp_path / 'store.tar.gz'
        manifest = tmp_path / 'manifest.json'
        manifest.write_text(json.dumps({'sha256': pack_backup(dump, uploads, bundle)}), encoding='utf-8')
        restored = extract_backup(bundle, manifest, tmp_path / 'restored')
        # Only this disposable fixture database is reset; production is rejected above.
        with app.app_context():
            db.session.remove()
            db.drop_all()
            db.engine.dispose()
        with (restored / 'database.sql').open('rb') as source:
            subprocess.run([str(Path(client_dir) / ('mysql' + extension)),
                f'--defaults-extra-file={defaults}', url.database], stdin=source,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True, timeout=60)
        with app.app_context():
            assert db.session.get(Product, product.id).name == 'QA restore sentinel'
            assert db.session.scalar(db.select(db.func.count()).select_from(Product)) == 1
        assert (restored / 'uploads/sentinel.txt').read_text(encoding='utf-8') == 'Synthetic upload only'
    finally:
        defaults.unlink(missing_ok=True)
