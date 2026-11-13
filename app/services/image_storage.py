import io
import secrets
from pathlib import Path
from PIL import Image, UnidentifiedImageError
from werkzeug.datastructures import FileStorage
from flask import current_app

ALLOWED = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}
MAX_PIXELS = 20_000_000

def save_product_image(file: FileStorage):
    if not file or not file.filename: raise ValueError("No image supplied.")
    if file.mimetype not in ALLOWED: raise ValueError("Unsupported image type.")
    raw = file.stream.read(current_app.config["MAX_CONTENT_LENGTH"] + 1)
    if len(raw) > current_app.config["MAX_CONTENT_LENGTH"]: raise ValueError("Image is too large.")
    try:
        image = Image.open(io.BytesIO(raw), formats=["JPEG", "PNG", "WEBP"])
        image.verify()
        image = Image.open(io.BytesIO(raw), formats=["JPEG", "PNG", "WEBP"])
    except (UnidentifiedImageError, OSError) as exc: raise ValueError("Invalid image.") from exc
    if image.width * image.height > MAX_PIXELS: raise ValueError("Image dimensions are too large.")
    image = image.convert("RGB")
    image.thumbnail((2400, 2400), Image.Resampling.LANCZOS)
    key = f"products/{secrets.token_hex(24)}.webp"
    destination = Path(current_app.config["UPLOAD_DIR"]) / key
    destination.parent.mkdir(parents=True, exist_ok=True)
    image.save(destination, "WEBP", quality=85, method=6)
    return key, "image/webp", destination.stat().st_size, image.width, image.height
