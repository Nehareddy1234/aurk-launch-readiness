"""Decode and re-encode customer photos, discarding metadata and filenames."""
from io import BytesIO
from pathlib import Path
from uuid import uuid4
import warnings
from flask import current_app
from PIL import Image, ImageOps, UnidentifiedImageError

MAX_PHOTO_BYTES = 8 * 1024 * 1024

def save_customer_photo(upload):
    if not upload or not upload.filename:
        raise ValueError("Choose a JPG, PNG or WEBP photo.")
    data = upload.read(MAX_PHOTO_BYTES + 1)
    if not data or len(data) > MAX_PHOTO_BYTES:
        raise ValueError("Choose a non-empty photo no larger than 8 MB.")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(data), formats=["JPEG", "PNG", "WEBP"]) as source:
                if source.width * source.height > 20_000_000:
                    raise ValueError("Use a photo smaller than 20 megapixels.")
                source.load()
                image = ImageOps.exif_transpose(source).convert("RGB")
                image.thumbnail((1800, 2400))
                clean = Image.new("RGB", image.size)
                clean.paste(image)
                output = BytesIO()
                clean.save(output, format="JPEG", quality=88, optimize=True)
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise ValueError("Upload a valid JPG, PNG or WEBP photo.") from None
    key = f"customer-photos/{uuid4().hex}.jpg"
    path = Path(current_app.config["UPLOAD_DIR"]) / key
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(output.getvalue())
    return key
