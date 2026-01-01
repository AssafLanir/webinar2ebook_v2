"""Image processing utilities using Pillow.

Provides:
- Thumbnail generation (max 512px)
- SHA-256 hash computation
- Image dimension extraction
- EPUB image conversion (WebP → JPEG/PNG)
- EPUB image optimization (downscale large images)
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


# =============================================================================
# EPUB Image Conversion (Spec 007)
# =============================================================================

# Maximum dimension (width or height) for EPUB images
# Keeps file size reasonable while maintaining quality
MAX_EPUB_DIMENSION = 1600

# JPEG quality for EPUB images
EPUB_JPEG_QUALITY = 85


def convert_for_epub(image_bytes: bytes, mime_type: str) -> Tuple[bytes, str]:
    """Convert image to EPUB-compatible format if needed.

    EPUB 3.0 supports: JPEG, PNG, GIF, SVG
    WebP is not universally supported by e-readers.

    Args:
        image_bytes: Raw image bytes
        mime_type: Original MIME type (e.g., "image/webp")

    Returns:
        Tuple of (converted_bytes, new_mime_type)
    """
    # Pass through already-compatible formats
    if mime_type in ("image/jpeg", "image/png", "image/gif"):
        return image_bytes, mime_type

    # Convert WebP or other formats
    with Image.open(io.BytesIO(image_bytes)) as img:
        # Optimize size first
        img = optimize_epub_image_size(img)

        output = io.BytesIO()

        # Use PNG if image has alpha channel, otherwise JPEG
        if _has_alpha(img):
            # Convert to RGBA if needed for PNG with alpha
            if img.mode not in ("RGBA", "LA"):
                img = img.convert("RGBA")
            img.save(output, format="PNG", optimize=True)
            return output.getvalue(), "image/png"
        else:
            # Convert to RGB for JPEG (handles RGBA, P, L, etc.)
            if img.mode != "RGB":
                img = img.convert("RGB")
            img.save(output, format="JPEG", quality=EPUB_JPEG_QUALITY, optimize=True)
            return output.getvalue(), "image/jpeg"


def optimize_epub_image_size(img: Image.Image) -> Image.Image:
    """Downscale large images for reasonable EPUB file size.

    Images larger than MAX_EPUB_DIMENSION in either dimension are
    scaled down while preserving aspect ratio.

    Args:
        img: PIL Image object

    Returns:
        Optimized PIL Image object (may be the same object if no resize needed)
    """
    if max(img.size) > MAX_EPUB_DIMENSION:
        # thumbnail() modifies in place and preserves aspect ratio
        img.thumbnail((MAX_EPUB_DIMENSION, MAX_EPUB_DIMENSION), Image.Resampling.LANCZOS)
    return img


def optimize_and_convert_for_epub(image_bytes: bytes, mime_type: str) -> Tuple[bytes, str]:
    """Optimize and convert image for EPUB in one step.

    Combines size optimization and format conversion.

    Args:
        image_bytes: Raw image bytes
        mime_type: Original MIME type

    Returns:
        Tuple of (optimized_bytes, new_mime_type)
    """
    # If already compatible, just optimize size if needed
    if mime_type in ("image/jpeg", "image/png", "image/gif"):
        with Image.open(io.BytesIO(image_bytes)) as img:
            # Check if optimization is needed
            if max(img.size) <= MAX_EPUB_DIMENSION:
                return image_bytes, mime_type

            # Optimize size
            img = optimize_epub_image_size(img)
            output = io.BytesIO()

            if mime_type == "image/jpeg":
                if img.mode != "RGB":
                    img = img.convert("RGB")
                img.save(output, format="JPEG", quality=EPUB_JPEG_QUALITY, optimize=True)
            elif mime_type == "image/png":
                img.save(output, format="PNG", optimize=True)
            else:  # GIF
                img.save(output, format="GIF")

            return output.getvalue(), mime_type

    # Convert and optimize WebP/other formats
    return convert_for_epub(image_bytes, mime_type)


def get_epub_image_extension(mime_type: str) -> str:
    """Get file extension for a MIME type (EPUB context).

    Args:
        mime_type: Image MIME type

    Returns:
        File extension without dot (e.g., "jpg", "png")
    """
    extensions = {
        "image/jpeg": "jpg",
        "image/png": "png",
        "image/gif": "gif",
        "image/webp": "webp",
        "image/svg+xml": "svg",
    }
    return extensions.get(mime_type, "jpg")


def _has_alpha(img: Image.Image) -> bool:
    """Check if image has an alpha channel.

    Args:
        img: PIL Image object

    Returns:
        True if image has alpha channel
    """
    if img.mode in ("RGBA", "LA"):
        return True
    if img.mode == "P" and "transparency" in img.info:
        return True
    return False
