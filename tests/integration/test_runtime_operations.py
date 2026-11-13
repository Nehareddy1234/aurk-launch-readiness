from datetime import datetime, timedelta, timezone
from unittest.mock import Mock
import pytest
from app import create_app
from app.extensions import db
from app.models import ProductInterest, CustomerEmail
from app.services import product_interests
from app.services.runtime_health import EXPECTED_SCHEMA_REVISION


def test_unknown_environment_never_falls_back_to_debug():
    with pytest.raises(RuntimeError, match="Unknown FLASK_CONFIG"):
        create_app("prodution")


@pytest.mark.parametrize("field,value", [("SECRET_KEY", "short"), ("SESSION_COOKIE_SECURE", False), ("WTF_CSRF_ENABLED", False)])
def test_unsafe_production_configuration_fails_closed(monkeypatch, field, value):
    from app.config import ProductionConfig
    monkeypatch.setattr(ProductionConfig, "SECRET_KEY", "test-only-valid-length-key-1234567890")
    monkeypatch.setattr(ProductionConfig, "SQLALCHEMY_DATABASE_URI", "sqlite:///:memory:")
    monkeypatch.setattr(ProductionConfig, "SESSION_COOKIE_SECURE", True)
    monkeypatch.setattr(ProductionConfig, "REMEMBER_COOKIE_SECURE", True)
    monkeypatch.setattr(ProductionConfig, field, value)
    with pytest.raises(RuntimeError, match="Production"):
        create_app("production")


def test_readiness_checks_schema_without_exposing_private_details(app, client):
    app.config["REQUIRE_SCHEMA_REVISION"] = True
    with app.app_context():
        db.session.execute(db.text("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)"))
        db.session.execute(db.text("INSERT INTO alembic_version VALUES ('old-release')"))
        db.session.commit()
    response = client.get('/api/ready')
    assert response.status_code == 503 and response.json == {'status': 'unavailable'}
    assert b'old-release' not in response.data
    with app.app_context():
        db.session.execute(db.text("UPDATE alembic_version SET version_num=:revision"), {'revision': EXPECTED_SCHEMA_REVISION})
        db.session.commit()
    assert client.get('/api/ready').status_code == 200


def test_readiness_detects_shared_limiter_failure(app, client, monkeypatch):
    import redis
    app.config.update(RATELIMIT_STORAGE_URI='redis://127.0.0.1:6379/0', RATELIMIT_ENABLED=True)
    factory=Mock(side_effect=TimeoutError('private connection information'))
    monkeypatch.setattr(redis.Redis, 'from_url', factory)
    response=client.get('/api/ready')
    assert response.status_code==503 and response.json=={'status':'unavailable'}
    assert b'private connection' not in response.data
    assert client.get('/api/health').status_code==200


def test_readiness_detects_missing_upload_volume(app, client, tmp_path):
    app.config['UPLOAD_DIR']=str(tmp_path/'unmounted-volume')
    assert client.get('/api/ready').status_code==503


def make_interest(app, qa_factory):
    product=qa_factory.product(product_status='coming_soon')
    with app.app_context():
        row=ProductInterest(product_id=product.id,identity_key='qa:retry',product_status='coming_soon')
        db.session.add(row);db.session.commit()
        return row.id


def test_interest_retries_back_off_and_stop_after_five(app, qa_factory, monkeypatch):
    ident=make_interest(app,qa_factory)
    sender=Mock(side_effect=RuntimeError('configuration failure'))
    monkeypatch.setattr(product_interests,'send_email',sender)
    with app.app_context():
        for attempt in range(1,6):
            assert product_interests.dispatch_interest_alerts()==0
            row=db.session.get(ProductInterest,ident)
            assert row.notification_attempts==attempt
            product_interests.dispatch_interest_alerts()
            assert sender.call_count==attempt
            row.notification_next_attempt_at=datetime.now(timezone.utc)-timedelta(seconds=1)
            db.session.commit()
        product_interests.dispatch_interest_alerts()
    assert sender.call_count==5
    result=app.test_cli_runner().invoke(args=['check-operations'])
    assert result.exit_code!=0 and 'exhausted=1' in result.output


def test_interest_uncertain_delivery_requires_review(app,qa_factory,monkeypatch):
    ident=make_interest(app,qa_factory)
    sender=Mock(side_effect=TimeoutError('provider may have accepted'))
    monkeypatch.setattr(product_interests,'send_email',sender)
    with app.app_context():
        product_interests.dispatch_interest_alerts()
        row=db.session.get(ProductInterest,ident)
        row.notification_next_attempt_at=datetime.now(timezone.utc)-timedelta(seconds=1)
        db.session.commit()
        product_interests.notify_interest(ident)
        product_interests.dispatch_interest_alerts()
    sender.assert_called_once()
    result=app.test_cli_runner().invoke(args=['check-operations'])
    assert result.exit_code!=0 and 'uncertain=1' in result.output
    runner = app.test_cli_runner()
    assert runner.invoke(args=['retry-interest-alert',str(ident)]).exit_code != 0
    assert runner.invoke(args=['retry-interest-alert',str(ident),'--reviewed']).exit_code == 0
    sender.assert_called_once()
    with app.app_context():
        row=db.session.get(ProductInterest,ident)
        assert row.notification_attempts==0 and row.notification_last_error is None


def test_operations_reports_stale_queue_without_sending_or_disclosing_email(app,qa_factory,mocked_smtp):
    user=qa_factory.customer()
    with app.app_context():
        db.session.add(CustomerEmail(event_key='welcome:stale',kind='welcome',user_id=user.id,recipient='private@example.com',created_at=datetime.now(timezone.utc)-timedelta(hours=1)))
        db.session.commit()
    result=app.test_cli_runner().invoke(args=['check-operations'])
    assert result.exit_code!=0 and 'stale=1' in result.output
    assert 'private@example.com' not in result.output
    mocked_smtp.assert_not_called()


def test_operations_empty_queues_pass(app):
    result=app.test_cli_runner().invoke(args=['check-operations'])
    assert result.exit_code==0,result.output


def test_deployment_flags_active_qa_products_only(app, qa_factory):
    qa_factory.product()
    qa_factory.product(is_active=False)
    qa_factory.product(is_archived=True)
    with app.app_context():
        db.session.execute(db.text("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)"))
        db.session.execute(db.text("INSERT INTO alembic_version VALUES (:revision)"), {'revision': EXPECTED_SCHEMA_REVISION})
        db.session.commit()
    result = app.test_cli_runner().invoke(args=['check-deployment', '--technical-only'])
    assert result.exit_code != 0
    assert 'Review/archive 1 active QA catalogue product(s)' in result.output


def test_mysql_overlapping_interest_workers_send_once(app,qa_factory,monkeypatch):
    with app.app_context():
        if db.engine.dialect.name!='mysql': pytest.skip('Requires MySQL row locking')
    ident=make_interest(app,qa_factory)
    sender=Mock();monkeypatch.setattr(product_interests,'send_email',sender)
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    barrier=Barrier(2)
    def work():
        with app.app_context():
            barrier.wait(timeout=5)
            return product_interests.notify_interest(ident)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(lambda _:work(),range(2)))
    assert sum(results)==1
    sender.assert_called_once()
