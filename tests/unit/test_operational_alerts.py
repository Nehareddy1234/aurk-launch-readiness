from types import SimpleNamespace
from unittest.mock import MagicMock
import json
import pytest
from scripts import operational_alert, check_host_health


@pytest.fixture
def alert_config():
    return dict(MAIL_SERVER="smtp.example.test", MAIL_FROM="sender@example.test",
                MAIL_USERNAME="test-user", MAIL_PASSWORD="private-test-value",
                MAIL_USE_TLS="true", MAIL_USE_SSL="false", MAIL_PORT="587",
                AURK_ALERT_EMAIL="operator@example.test")


def smtp_mock(monkeypatch):
    connection = MagicMock()
    connection.__enter__.return_value.send_message.return_value = {}
    factory = MagicMock(return_value=connection)
    monkeypatch.setattr(operational_alert.smtplib, "SMTP", factory)
    return factory, connection.__enter__.return_value


def test_alert_uses_tls_and_limits_repeated_attempts(monkeypatch, tmp_path, alert_config):
    factory, smtp = smtp_mock(monkeypatch)
    assert operational_alert.send_alert("aurk-health.service", alert_config, tmp_path, now=10000)
    assert not operational_alert.send_alert("aurk-health.service", alert_config, tmp_path, now=10001)
    assert operational_alert.send_alert("aurk-health.service", alert_config, tmp_path, now=13600)
    assert factory.call_count == 2
    smtp.starttls.assert_called()
    smtp.login.assert_called_with("test-user", "private-test-value")
    message = smtp.send_message.call_args.args[0]
    assert "aurk-health.service" in message.get_content()
    assert "private-test-value" not in message.as_string()


def test_uncertain_smtp_outcome_is_not_immediately_repeated(monkeypatch, tmp_path, alert_config):
    factory, smtp = smtp_mock(monkeypatch)
    smtp.send_message.side_effect = TimeoutError("provider may have accepted")
    with pytest.raises(TimeoutError):
        operational_alert.send_alert("aurk-backup.service", alert_config, tmp_path, now=10000)
    assert not operational_alert.send_alert("aurk-backup.service", alert_config, tmp_path, now=10001)
    factory.assert_called_once()


def test_refused_alert_is_not_reported_as_submitted(monkeypatch, tmp_path, alert_config):
    _, smtp = smtp_mock(monkeypatch)
    smtp.send_message.return_value = {"operator@example.test": (550, b"rejected")}
    with pytest.raises(RuntimeError, match="refused"):
        operational_alert.send_alert("aurk-backup.service", alert_config, tmp_path)


@pytest.mark.parametrize("unit", ["../../escape", "other.service", "aurk.service\nInjected"])
def test_alert_rejects_unknown_service_before_network(monkeypatch, tmp_path, alert_config, unit):
    factory, _ = smtp_mock(monkeypatch)
    with pytest.raises(ValueError, match="Unsupported"):
        operational_alert.send_alert(unit, alert_config, tmp_path)
    factory.assert_not_called()
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("tls,ssl", [("true", "true"), ("false", "false")])
def test_insecure_or_conflicting_transport_fails_closed(monkeypatch, tmp_path, alert_config, tls, ssl):
    alert_config.update(MAIL_USE_TLS=tls, MAIL_USE_SSL=ssl)
    factory, _ = smtp_mock(monkeypatch)
    with pytest.raises(ValueError, match="exactly one"):
        operational_alert.send_alert("aurk-health.service", alert_config, tmp_path)
    factory.assert_not_called()


def test_alert_requires_explicit_recipient(monkeypatch, tmp_path, alert_config):
    alert_config["AURK_ALERT_EMAIL"] = ""
    factory, _ = smtp_mock(monkeypatch)
    with pytest.raises(ValueError, match="recipient"):
        operational_alert.send_alert("aurk-health.service", alert_config, tmp_path)
    factory.assert_not_called()


@pytest.mark.parametrize("total,free", [(8, 1.1), (100, 5)])
def test_host_check_detects_absolute_and_proportional_disk_pressure(monkeypatch, tmp_path, total, free):
    monkeypatch.setattr(check_host_health.shutil, "disk_usage", lambda _: SimpleNamespace(total=total*1024**3, free=free*1024**3))
    with pytest.raises(ValueError):
        check_host_health.check_storage(tmp_path)


def test_host_check_rejects_missing_upload_directory(tmp_path):
    with pytest.raises(ValueError, match="missing"):
        check_host_health.check_storage(tmp_path / "missing")


def test_host_check_accepts_adequate_reserve(monkeypatch, tmp_path):
    monkeypatch.setattr(check_host_health.shutil, "disk_usage", lambda _: SimpleNamespace(total=20*1024**3, free=8*1024**3))
    assert check_host_health.check_storage(tmp_path) == 8*1024**3
