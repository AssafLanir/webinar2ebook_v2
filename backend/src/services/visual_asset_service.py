"""Visual asset service for upload, storage, and retrieval.

Handles:
- Processing uploaded images (validation, thumbnail, hash)
- Storing binaries in GridFS (original + thumbnail)
- Building VisualAsset metadata objects
- Deleting assets and their GridFS data
"""

from __future__ import annotations

import logging
import os
from datetime import UTC, datetime
from uuid import uuid4

from src.models.visuals import VisualAsset, VisualAssetOrigin
from src.services import gridfs_service
from src.services.image_utils import (
    compute_sha256,
    generate_thumbnail,
    get_image_dimensions,
    is_supported_image_type,
    normalize_media_type,
)

logger = logging.getLogger(__name__)

# Configuration
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
MAX_ASSETS_PER_PROJECT = 10
ALLOWED_MEDIA_TYPES = {"image/png", "image/jpeg", "image/webp"}


class UploadValidationError(Exception):
    """Raised when upload validation fails."""

    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)


async def process_and_store_asset(
    project_id: str,
    file_content: bytes,
    filename: str,
    media_type: str,
    caption: str | None = None,
) -> VisualAsset:
    """Process an uploaded image and store it in GridFS.

    Args:
        project_id: Project ID for ownership.
        file_content: Raw image bytes.
        filename: Original filename.
        media_type: MIME type (e.g., 'image/png').
        caption: Optional caption (defaults to filename without extension).

    Returns:
        VisualAsset with all fields populated.

    Raises:
        UploadValidationError: If validation fails (type, size).
        ValueError: If image processing fails.
    """
    # Normalize media type
    media_type = normalize_media_type(media_type)

    # Validate media type
    if not is_supported_image_type(media_type):
        raise UploadValidationError(
            code="UNSUPPORTED_MEDIA_TYPE",
            message=f"File '{filename}' is not a supported image type. Allowed: PNG, JPEG, WebP",
        )

    # Validate file size
    if len(file_content) > MAX_FILE_SIZE:
        raise UploadValidationError(
            code="UPLOAD_TOO_LARGE",
            message=f"File '{filename}' exceeds 10MB limit ({len(file_content) / 1024 / 1024:.1f}MB)",
        )

    # Generate asset ID
    asset_id = str(uuid4())

    # Compute hash
    sha256_hash = compute_sha256(file_content)

    # Get image dimensions
    width, height = get_image_dimensions(file_content)

    # Generate thumbnail
    thumb_bytes, thumb_media_type = generate_thumbnail(file_content)

    # Store original in GridFS
    original_storage_key = await gridfs_service.store_file(
        content=file_content,
        filename=f"{asset_id}_original",
        content_type=media_type,
        metadata={
            "project_id": project_id,
            "asset_id": asset_id,
            "variant": "original",
        },
    )

    # Store thumbnail in GridFS
    thumb_storage_key = await gridfs_service.store_file(
        content=thumb_bytes,
        filename=f"{asset_id}_thumb",
        content_type=thumb_media_type,
        metadata={
            "project_id": project_id,
            "asset_id": asset_id,
            "variant": "thumb",
        },
    )

    # Default caption = filename without extension
    if not caption:
        caption = os.path.splitext(filename)[0]

    # Build VisualAsset
    asset = VisualAsset(
        id=asset_id,
        filename=filename,
        media_type=media_type,
        origin=VisualAssetOrigin.client_provided,
        storage_key=original_storage_key,
        width=width,
        height=height,
        original_filename=filename,
        size_bytes=len(file_content),
        caption=caption,
        sha256=sha256_hash,
        created_at=datetime.now(UTC).isoformat(),
    )

    logger.info(
        f"Processed asset {asset_id}: {filename} ({width}x{height}, {len(file_content)} bytes)"
    )

    return asset


async def get_asset_content(
    project_id: str,
    asset_id: str,
    variant: str = "thumb",
) -> tuple[bytes, str] | None:
    """Retrieve asset content from GridFS.

    Args:
        project_id: Project ID for ownership verification.
        asset_id: Asset ID.
        variant: 'thumb' or 'full' (original).

    Returns:
        Tuple of (content_bytes, media_type) or None if not found.
    """
    # Map variant name to storage variant
    storage_variant = "original" if variant == "full" else "thumb"
    filename = f"{asset_id}_{storage_variant}"

    result = await gridfs_service.get_file_by_filename(filename)
    if result is None:
        return None

    content, media_type, metadata = result

    # Verify project ownership
    if metadata.get("project_id") != project_id:
        logger.warning(f"Project mismatch for asset {asset_id}: {metadata.get('project_id')} != {project_id}")
        return None

    return content, media_type


async def delete_asset_files(asset_id: str) -> int:
    """Delete all GridFS files for an asset (original + thumbnail).

    Args:
        asset_id: Asset ID.

    Returns:
        Number of files deleted.
    """
    deleted = await gridfs_service.delete_files_by_metadata({"asset_id": asset_id})
    logger.info(f"Deleted {deleted} GridFS files for asset {asset_id}")
    return deleted


def validate_asset_count(current_count: int, adding: int = 1) -> None:
    """Validate that adding assets won't exceed the limit.

    Args:
        current_count: Current number of assets in project.
        adding: Number of assets being added.

    Raises:
        UploadValidationError: If limit would be exceeded.
    """
    if current_count + adding > MAX_ASSETS_PER_PROJECT:
        raise UploadValidationError(
            code="TOO_MANY_ASSETS",
            message=f"Cannot add {adding} asset(s). Project already has {current_count} of {MAX_ASSETS_PER_PROJECT} maximum assets.",
        )
