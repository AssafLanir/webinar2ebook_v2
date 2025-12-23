"""Image processing utilities using Pillow.

Provides:
- Thumbnail generation (max 512px)
- SHA-256 hash computation
- Image dimension extraction
"""

from __future__ import annotations

import hashlib
import io
import logging
from typing import Tuple

from PIL import Image

logger = logging.getLogger(__name__)

# Constants
MAX_THUMBNAIL_SIZE = 512  # Maximum dimension (width or height) for thumbnails
THUMBNAIL_QUALITY = 85  # JPEG quality for thumbnails


def compute_sha256(data: bytes) -> str:
    """Compute SHA-256 hash of binary data.

    Args:
        data: Raw bytes to hash.

    Returns:
        Lowercase hex string of SHA-256 hash.
    """
    return hashlib.sha256(data).hexdigest()


def get_image_dimensions(data: bytes) -> Tuple[int, int]:
    """Extract width and height from image bytes.

    Args:
        data: Raw image bytes.

    Returns:
        Tuple of (width, height) in pixels.

    Raises:
        ValueError: If data is not a valid image.
    """
    try:
        with Image.open(io.BytesIO(data)) as img:
            return img.size  # (width, height)
    except Exception as e:
        raise ValueError(f"Cannot read image dimensions: {e}") from e


def generate_thumbnail(
    data: bytes,
    max_size: int = MAX_THUMBNAIL_SIZE,
    output_format: str | None = None,
) -> Tuple[bytes, str]:
    """Generate a thumbnail from image bytes.

    Resizes the image so that the largest dimension is at most `max_size` pixels,
    preserving aspect ratio.

    Args:
        data: Raw image bytes (PNG, JPEG, or WebP).
        max_size: Maximum width or height in pixels (default: 512).
        output_format: Output format ('PNG', 'JPEG', 'WEBP') or None to preserve.

    Returns:
        Tuple of (thumbnail_bytes, media_type).
        - thumbnail_bytes: The resized image as bytes.
        - media_type: MIME type (e.g., 'image/png').

    Raises:
        ValueError: If input is not a valid image.
    """
    try:
        with Image.open(io.BytesIO(data)) as img:
            # Determine output format
            if output_format:
                fmt = output_format.upper()
            else:
                # Preserve original format, fallback to PNG
                fmt = img.format or "PNG"

            # Map format to MIME type
            format_to_mime = {
                "PNG": "image/png",
                "JPEG": "image/jpeg",
                "JPG": "image/jpeg",
                "WEBP": "image/webp",
            }
            media_type = format_to_mime.get(fmt.upper(), "image/png")

            # Convert RGBA to RGB for JPEG (no alpha channel support)
            if fmt.upper() in ("JPEG", "JPG") and img.mode in ("RGBA", "LA", "P"):
                # Create white background for transparency
                background = Image.new("RGB", img.size, (255, 255, 255))
                if img.mode == "P":
                    img = img.convert("RGBA")
                background.paste(img, mask=img.split()[-1] if img.mode == "RGBA" else None)
                img = background

            # Only resize if larger than max_size
            width, height = img.size
            if width > max_size or height > max_size:
                # Calculate new size preserving aspect ratio
                ratio = min(max_size / width, max_size / height)
                new_size = (int(width * ratio), int(height * ratio))
                img = img.resize(new_size, Image.Resampling.LANCZOS)
                logger.debug(f"Resized image from {width}x{height} to {new_size[0]}x{new_size[1]}")

            # Save to bytes
            output = io.BytesIO()
            save_kwargs = {}
            if fmt.upper() in ("JPEG", "JPG"):
                save_kwargs["quality"] = THUMBNAIL_QUALITY
                save_kwargs["optimize"] = True
            elif fmt.upper() == "PNG":
                save_kwargs["optimize"] = True
            elif fmt.upper() == "WEBP":
                save_kwargs["quality"] = THUMBNAIL_QUALITY

            img.save(output, format=fmt, **save_kwargs)
            return output.getvalue(), media_type

    except Exception as e:
        raise ValueError(f"Cannot generate thumbnail: {e}") from e


def is_supported_image_type(media_type: str) -> bool:
    """Check if a MIME type is a supported image format.

    Args:
        media_type: MIME type string (e.g., 'image/png').

    Returns:
        True if supported (PNG, JPEG, WebP), False otherwise.
    """
    supported = {"image/png", "image/jpeg", "image/jpg", "image/webp"}
    return media_type.lower() in supported


def normalize_media_type(media_type: str) -> str:
    """Normalize MIME type to standard form.

    Args:
        media_type: Input MIME type.

    Returns:
        Normalized MIME type (e.g., 'image/jpg' -> 'image/jpeg').
    """
    if media_type.lower() == "image/jpg":
        return "image/jpeg"
    return media_type.lower()
