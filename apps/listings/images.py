"""Photo sanitizing: decode, rotate, resize, re-encode and drop all metadata.

Originals are never written to disk. Only the returned JPEG bytes are stored.
"""

import io
import warnings

from PIL import Image, ImageOps, UnidentifiedImageError

MAX_BYTES = 5 * 1024 * 1024
MAX_PIXELS = 12_000_000
MAX_EDGE = 1600
ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}


class ImageRejected(ValueError):
    pass


def sanitize_image(uploaded):
    """Return (jpeg_bytes, width, height) for a valid photo, or raise ImageRejected."""
    if uploaded.size > MAX_BYTES:
        raise ImageRejected("Each photo must be 5 MB or smaller.")
    data = uploaded.read()
    if len(data) > MAX_BYTES:
        raise ImageRejected("Each photo must be 5 MB or smaller.")

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(data)) as probe:
                if probe.format not in ALLOWED_FORMATS:
                    raise ImageRejected("Photos must be JPEG, PNG or WebP.")
                if probe.width * probe.height > MAX_PIXELS:
                    raise ImageRejected("Each photo must be 12 megapixels or smaller.")
                probe.verify()
            image = Image.open(io.BytesIO(data))
            image.load()
    except ImageRejected:
        raise
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError, Image.DecompressionBombWarning, Image.DecompressionBombError):
        raise ImageRejected("That file isn't a readable photo.")

    image = ImageOps.exif_transpose(image)
    if image.mode in ("RGBA", "LA") or (image.mode == "P" and "transparency" in image.info):
        rgba = image.convert("RGBA")
        image = Image.new("RGB", rgba.size, (255, 255, 255))
        image.paste(rgba, mask=rgba.getchannel("A"))
    else:
        image = image.convert("RGB")
    image.thumbnail((MAX_EDGE, MAX_EDGE), Image.LANCZOS)

    # A fresh image carries no EXIF, XMP, ICC or GPS data from the upload.
    clean = Image.new("RGB", image.size)
    clean.paste(image)
    out = io.BytesIO()
    clean.save(out, format="JPEG", quality=85, optimize=True)
    return out.getvalue(), clean.width, clean.height
