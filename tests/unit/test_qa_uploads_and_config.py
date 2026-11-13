from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import hashlib
import json
import re

import pytest
from PIL import Image
from werkzeug.datastructures import FileStorage

from app.services.customer_photos import save_customer_photo


@pytest.mark.parametrize("data,name", [(b"<?php echo 'bad'; ?>","image.jpg"),(b"MZ"+b"x"*30,"a.png"),(b"GIF89a","fake.jpg"),(b"","empty.jpg"),(b"\xff\xd8broken","broken.jpg"),(b"x"*(8*1024*1024+1),"large.jpg")], ids=["php","executable","gif","empty","corrupt","oversize"])
def test_customer_photo_rejects_invalid_content(app,data,name):
    with app.app_context(),pytest.raises(ValueError):
        save_customer_photo(FileStorage(stream=BytesIO(data),filename=name))
    assert not list(Path(app.config["UPLOAD_DIR"]).rglob("*.jpg"))


def test_customer_photo_strips_metadata_executable_tail_and_filename(app):
    image=Image.new("RGB",(30,40),"red");exif=Image.Exif();exif[270]="private metadata"
    content=BytesIO();image.save(content,format="JPEG",exif=exif)
    payload=content.getvalue()+b"<?php EXECUTABLE_TAIL ?>"
    with app.app_context():
        key=save_customer_photo(FileStorage(stream=BytesIO(payload),filename="../../outside.php.jpg"))
    path=Path(app.config["UPLOAD_DIR"])/key
    assert path.resolve().is_relative_to(Path(app.config["UPLOAD_DIR"]).resolve())
    assert re.fullmatch(r"customer-photos/[0-9a-f]{32}\.jpg",key)
    assert b"EXECUTABLE_TAIL" not in path.read_bytes()
    with Image.open(path) as result:
        assert result.format=="JPEG" and not result.getexif()


def test_customer_photo_rejects_dimensions_above_limit(app):
    output=BytesIO();Image.new("RGB",(5000,4001),"white").save(output,format="PNG")
    # Either the service limit or Pillow's decompression-bomb guard may reject
    # first. Both must reject the upload and leave no file behind.
    with app.app_context(),pytest.raises(ValueError):
        save_customer_photo(FileStorage(stream=BytesIO(output.getvalue()),filename="huge.png"))
    assert not list(Path(app.config["UPLOAD_DIR"]).rglob("*.jpg"))


def test_production_config_boots_with_dummy_values_without_database_connection(tmp_path,monkeypatch):
    from app import create_app
    from app.config import ProductionConfig
    monkeypatch.setattr(ProductionConfig,"SECRET_KEY","qa-dummy-secret-not-a-live-key-32-chars")
    monkeypatch.setattr(ProductionConfig,"SQLALCHEMY_DATABASE_URI","sqlite:///:memory:")
    monkeypatch.setattr(ProductionConfig,"SQLALCHEMY_ENGINE_OPTIONS",{})
    monkeypatch.setattr(ProductionConfig,"UPLOAD_DIR",str(tmp_path/"qa-prod-uploads"))
    monkeypatch.setattr(ProductionConfig,"MAIL_SERVER","")
    monkeypatch.setattr(ProductionConfig,"CUSTOMER_EMAILS_ENABLED",False)
    monkeypatch.chdir(tmp_path)
    (tmp_path/"instance").mkdir()
    app=create_app("production")
    assert not app.debug and not app.testing
    assert app.config["SESSION_COOKIE_HTTPONLY"]
    assert app.config["SESSION_COOKIE_SAMESITE"]=="Lax"
    # Close the production log handler before tmp_path cleanup on Windows.
    for handler in list(app.logger.handlers):
        if getattr(handler,"baseFilename","").startswith(str(tmp_path)):
            handler.close();app.logger.removeHandler(handler)


def test_known_limitations_are_explicit_not_fabricated_features():
    config=Path("app/config.py").read_text()
    checkout=Path("app/checkout/routes.py").read_text()
    status=Path("app/services/order_status.py").read_text()
    assert 'provider="cash_on_delivery"' in checkout
    assert '100 * 1024 * 1024' in config
    # Availability/lifecycle messages are covered by behavioral integration tests.
    assert 'notify_interest' in Path("app/models/customer_email.py").read_text()
    assert '"drop_live"' not in Path("app/services/customer_emails.py").read_text()


def test_no_known_live_secret_patterns_in_application_source():
    findings=[]
    patterns=[r"xsmtpsib-[A-Za-z0-9_-]{30,}",r"AKIA[0-9A-Z]{16}",r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"]
    for folder in ("app","migrations","scripts"):
        for path in Path(folder).rglob("*.py"):
            for number,line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(),1):
                if any(re.search(pattern,line) for pattern in patterns): findings.append(f"{path}:{number}")
    assert not findings,findings


def test_password_reset_token_expiry_with_frozen_time(app,frozen_time):
    from app.security.tokens import make_token, read_token
    from itsdangerous import SignatureExpired
    with app.app_context():
        token=make_token("qa-user:qa-fingerprint","password-reset")
        assert read_token(token,"password-reset",1800)=="qa-user:qa-fingerprint"
        frozen_time.tick(1801)
        with pytest.raises(SignatureExpired): read_token(token,"password-reset",1800)
