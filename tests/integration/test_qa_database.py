from pathlib import Path
import json

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models import ProductInterest, CustomerEmail, User


def test_latest_migration_roundtrip_and_single_head(app):
    from alembic.config import Config
    from alembic.script import ScriptDirectory
    config=Config();config.set_main_option("script_location","migrations")
    assert ScriptDirectory.from_config(config).get_heads()==["d4ab72cd5610"]
    with app.app_context(): db.drop_all()
    runner=app.test_cli_runner()
    for args in (["db","upgrade"],["db","downgrade","89bc27de0165"],["db","upgrade"]):
        result=runner.invoke(args=args)
        assert result.exit_code==0,result.output
    with app.app_context():
        assert db.session.execute(text("SELECT version_num FROM alembic_version")).scalar()=="d4ab72cd5610"


def test_QA_DB_001_models_match_fresh_migration_schema(app):
    from alembic.autogenerate import compare_metadata
    from alembic.migration import MigrationContext
    with app.app_context(): db.drop_all()
    result=app.test_cli_runner().invoke(args=["db","upgrade"])
    assert result.exit_code==0,result.output
    with app.app_context(),db.engine.connect() as connection:
        context=MigrationContext.configure(connection,opts={"compare_type":True,"compare_server_default":True})
        differences=compare_metadata(context,db.metadata)
        Path("qa_artifacts").mkdir(exist_ok=True)
        Path(f"qa_artifacts/schema-differences-{connection.dialect.name}.txt").write_text("\n".join(map(str,differences)),encoding="utf-8")
        assert not differences, "QA-DB-001: model/migration drift; see qa_artifacts/schema-differences.txt"


def test_database_unique_email_and_sku(app,qa_factory,customer):
    variant=qa_factory.variant()
    with app.app_context():
        existing=db.session.get(User,customer.id)
        duplicate=User(email=existing.email,first_name="Duplicate",last_name="QA",password_hash="not-plaintext-user-input")
        db.session.add(duplicate)
        with pytest.raises(IntegrityError): db.session.commit()
        db.session.rollback()
        from app.models import ProductVariant
        other=qa_factory.variant()
        db.session.get(ProductVariant,other.id).sku=variant.sku
        with pytest.raises(IntegrityError): db.session.commit()
        db.session.rollback()


def test_sqlite_foreign_keys_reject_invalid_interest_and_cascade_customer_email(app,qa_factory,customer):
    with app.app_context():
        if db.engine.dialect.name=="sqlite":
            db.session.execute(text("PRAGMA foreign_keys=ON"));db.session.commit()
        db.session.add(ProductInterest(product_id=999999,customer_id=customer.id,identity_key="qa-invalid",product_status="coming_soon"))
        with pytest.raises(IntegrityError): db.session.commit()
        db.session.rollback()
        db.session.add(CustomerEmail(event_key="welcome:qa",kind="welcome",user_id=customer.id,recipient=customer.email))
        db.session.commit()
        db.session.execute(db.delete(User).where(User.id==customer.id));db.session.commit()
        assert CustomerEmail.query.count()==0
