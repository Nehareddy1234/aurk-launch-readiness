"""Validate MP4 container structure before storing product videos."""
from pathlib import Path
from uuid import uuid4
from flask import current_app

MAX_VIDEO_SIZE = 25 * 1024 * 1024

def boxes(data):
    offset = 0
    while offset < len(data):
        if len(data) - offset < 8:
            raise ValueError("Invalid MP4 container.")
        size = int.from_bytes(data[offset:offset + 4], "big")
        kind = data[offset + 4:offset + 8]
        header = 8
        if size == 1:
            if len(data) - offset < 16:
                raise ValueError("Invalid MP4 container.")
            size = int.from_bytes(data[offset + 8:offset + 16], "big")
            header = 16
        elif size == 0:
            size = len(data) - offset
        if size < header or offset + size > len(data):
            raise ValueError("Invalid MP4 container.")
        yield kind, data[offset + header:offset + size]
        offset += size

def save_product_video(file, product_id, sort_order, *, storage_prefix=None):
    file.stream.seek(0)
    data = file.read(MAX_VIDEO_SIZE + 1)
    if len(data) > MAX_VIDEO_SIZE:
        raise ValueError("Each video must be 25 MB or smaller.")
    top = dict(boxes(data))
    brands = top.get(b"ftyp", b"")
    if len(brands) < 8 or not ({b"isom", b"iso2", b"mp41", b"mp42", b"avc1"} & {brands[:4], *[brands[i:i+4] for i in range(8, len(brands), 4)]}):
        raise ValueError("Upload a valid MP4 video.")
    if not top.get(b"mdat") or not top.get(b"moov"):
        raise ValueError("Upload a complete MP4 video.")
    dimensions = None
    for kind, track in boxes(top[b"moov"]):
        if kind != b"trak":
            continue
        parts = dict(boxes(track))
        media = dict(boxes(parts.get(b"mdia", b"")))
        if media.get(b"hdlr", b"")[8:12] != b"vide":
            continue
        header = parts.get(b"tkhd", b"")
        if len(header) >= 84:
            width = int.from_bytes(header[-8:-4], "big") >> 16
            height = int.from_bytes(header[-4:], "big") >> 16
            if width and height:
                dimensions = width, height
    if dimensions is None:
        raise ValueError("The MP4 must contain a video track.")
    key = f"{storage_prefix or f'products/{product_id}'}/{uuid4().hex}.mp4"
    path = Path(current_app.config["UPLOAD_DIR"]) / key
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return dict(storage_key=key, mime_type="video/mp4", file_size=len(data), width=dimensions[0], height=dimensions[1], sort_order=sort_order)
