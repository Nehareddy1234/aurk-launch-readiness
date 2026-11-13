import io
from pathlib import Path
import pytest
from werkzeug.datastructures import FileStorage
from app.admin.routes import save_product_image
from app.services.product_video import MAX_VIDEO_SIZE

def box(kind, payload):
    return (len(payload) + 8).to_bytes(4, "big") + kind + payload

def container(handler=b"vide"):
    header = bytes(76) + (640 << 16).to_bytes(4, "big") + (800 << 16).to_bytes(4, "big")
    track = box(b"tkhd", header) + box(b"mdia", box(b"hdlr", bytes(8) + handler + bytes(12)))
    return box(b"ftyp", b"isom" + bytes(4) + b"mp42") + box(b"moov", box(b"trak", track)) + box(b"mdat", b"payload")

def test_mp4_storage(app, tmp_path):
    app.config["UPLOAD_DIR"] = str(tmp_path)
    with app.app_context():
        result = save_product_image(FileStorage(stream=io.BytesIO(container()), filename="../../clip.mp4"), 42, 2)
    assert result["mime_type"] == "video/mp4"
    assert (result["width"], result["height"]) == (640, 800)
    assert result["sort_order"] == 2
    assert (tmp_path / result["storage_key"]).read_bytes() == container()
    assert result["storage_key"].startswith("products/42/")

@pytest.mark.parametrize("data", [b"not a video", container(b"soun"), container()[:-3], b"x" * (MAX_VIDEO_SIZE + 1)], ids=["invalid", "audio-only", "truncated", "oversized"])
def test_reject_invalid_video(app, tmp_path, data):
    app.config["UPLOAD_DIR"] = str(tmp_path)
    with app.app_context(), pytest.raises(ValueError):
        save_product_image(FileStorage(stream=io.BytesIO(data), filename="fake.mp4"), 42, 0)
    assert not list(tmp_path.rglob("*.mp4"))


def test_video_does_not_replace_photo_cover():
    from app.models import Product, ProductImage
    video = ProductImage(mime_type="video/mp4", is_primary=True)
    photo = ProductImage(mime_type="image/jpeg", is_primary=False)
    product = Product(images=[video, photo])
    assert product.primary_image is photo
    product.images = [video]
    assert product.primary_image is None


def test_gallery_excludes_video_from_photo_slider(app):
    from app.models import Product, ProductImage
    from flask import render_template
    photo = ProductImage(id=1, mime_type="image/jpeg", is_primary=True)
    second = ProductImage(id=2, mime_type="image/jpeg", is_primary=False)
    video = ProductImage(id=3, mime_type="video/mp4", is_primary=False)
    product = Product(name="Test", images=[photo, second, video])
    with app.test_request_context():
        html = render_template("shop/_photo_controls.html", product=product)
    assert "Photo 1 of 2" in html
    assert html.count("data-photo-source=") == 2
