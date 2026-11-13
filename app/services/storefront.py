"""Published homepage content and validated, private-on-disk marketing uploads."""
from copy import deepcopy
from io import BytesIO
from pathlib import Path
from uuid import uuid4
import warnings

from flask import current_app
from PIL import Image, ImageOps, UnidentifiedImageError
from app.extensions import db
from app.models.storefront import StorefrontContent

DEFAULTS = dict(cover_enabled=True, cover_title="MORE\nTHAN FITS",
                cover_subtitle="CLOTHES FOR A BIGGER TOMORROW", cover_button="SHOP NOW",
                cover_link="/shop", desktop_video="", mobile_video="", second_desktop_video="", second_mobile_video="", poster="",
                bar_enabled=False, bar_messages="", bar_link="/shop", bar_speed="normal",
                banners=[dict(enabled=False, image="", title="", alt="", link="/shop") for _ in range(3)])


def get_content():
    row = db.session.get(StorefrontContent, 1)
    content = deepcopy(DEFAULTS)
    if row:
        content.update(row.content)
    return content


def local_link(value):
    value = (value or "").strip()
    if not value.startswith("/") or value.startswith("//") or any(
        ord(c) < 32 or c in "\\" for c in value
    ):
        raise ValueError("Links must be local paths, for example /shop or /shop?category=tees.")
    return value


def save_image(upload):
    data = upload.read(8 * 1024 * 1024 + 1)
    if not data or len(data) > 8 * 1024 * 1024:
        raise ValueError("Each image must be non-empty and no larger than 8 MB.")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(data), formats=["JPEG", "PNG", "WEBP"]) as source:
                if source.width * source.height > 20_000_000:
                    raise ValueError("Use images no larger than 20 megapixels.")
                source.load()
                image = ImageOps.exif_transpose(source).convert("RGB")
                image.thumbnail((2560, 2560))
                output = BytesIO()
                image.save(output, "JPEG", quality=88)
    except (UnidentifiedImageError, OSError, Image.DecompressionBombWarning, Image.DecompressionBombError):
        raise ValueError("Upload a valid JPG, PNG or WEBP image.") from None
    key = f"storefront/{uuid4().hex}.jpg"
    target = Path(current_app.config["UPLOAD_DIR"]) / key
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(output.getvalue())
    return key


def media_keys(content):
    return {content.get(field) for field in ("desktop_video", "mobile_video", "second_desktop_video", "second_mobile_video", "poster")} | {
        banner.get("image") for banner in content["banners"]
    }
