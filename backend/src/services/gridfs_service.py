"""GridFS service for storing and retrieving binary files.

Provides async operations for:
- Storing original images and thumbnails
- Retrieving file content by ID
- Deleting files
- Listing files by metadata
"""

from __future__ import annotations

import logging
from typing import Any

from bson import ObjectId
from gridfs import NoFile
from motor.motor_asyncio import AsyncIOMotorGridFSBucket

from src.db.mongo import get_gridfs_bucket

logger = logging.getLogger(__name__)


async def store_file(
    content: bytes,
    filename: str,
    content_type: str,
    metadata: dict[str, Any] | None = None,
    bucket_name: str = "visuals",
) -> str:
    """Store a file in GridFS.

    Args:
        content: File bytes to store.
        filename: Name for the file (used for retrieval).
        content_type: MIME type (e.g., "image/png").
        metadata: Optional metadata dict (e.g., project_id, asset_id, variant).
        bucket_name: GridFS bucket name (default: "visuals").

    Returns:
        String representation of the GridFS file ID.
    """
    bucket = await get_gridfs_bucket(bucket_name)

    file_id = await bucket.upload_from_stream(
        filename,
        content,
        metadata={
            "content_type": content_type,
            **(metadata or {}),
        },
    )

    logger.info(f"Stored file {filename} ({len(content)} bytes) -> {file_id}")
    return str(file_id)


async def get_file(
    file_id: str,
    bucket_name: str = "visuals",
) -> tuple[bytes, str, dict[str, Any]] | None:
    """Retrieve a file from GridFS.

    Args:
        file_id: GridFS file ID (string).
        bucket_name: GridFS bucket name (default: "visuals").

    Returns:
        Tuple of (content bytes, content_type, metadata) or None if not found.
    """
    bucket = await get_gridfs_bucket(bucket_name)

    try:
        grid_out = await bucket.open_download_stream(ObjectId(file_id))
        content = await grid_out.read()
        metadata = grid_out.metadata or {}
        content_type = metadata.get("content_type", "application/octet-stream")

        return content, content_type, metadata
    except NoFile:
        logger.warning(f"File not found: {file_id}")
        return None
    except Exception as e:
        logger.error(f"Error retrieving file {file_id}: {e}")
        return None


async def get_file_by_filename(
    filename: str,
    bucket_name: str = "visuals",
) -> tuple[bytes, str, dict[str, Any]] | None:
    """Retrieve a file from GridFS by filename.

    Args:
        filename: The filename to search for.
        bucket_name: GridFS bucket name (default: "visuals").

    Returns:
        Tuple of (content bytes, content_type, metadata) or None if not found.
    """
    bucket = await get_gridfs_bucket(bucket_name)

    try:
        grid_out = await bucket.open_download_stream_by_name(filename)
        content = await grid_out.read()
        metadata = grid_out.metadata or {}
        content_type = metadata.get("content_type", "application/octet-stream")

        return content, content_type, metadata
    except NoFile:
        logger.warning(f"File not found by name: {filename}")
        return None
    except Exception as e:
        logger.error(f"Error retrieving file by name {filename}: {e}")
        return None


async def delete_file(
    file_id: str,
    bucket_name: str = "visuals",
) -> bool:
    """Delete a file from GridFS.

    Args:
        file_id: GridFS file ID (string).
        bucket_name: GridFS bucket name (default: "visuals").

    Returns:
        True if deleted, False if not found or error.
    """
    bucket = await get_gridfs_bucket(bucket_name)

    try:
        await bucket.delete(ObjectId(file_id))
        logger.info(f"Deleted file: {file_id}")
        return True
    except Exception as e:
        logger.error(f"Error deleting file {file_id}: {e}")
        return False


async def delete_files_by_metadata(
    metadata_filter: dict[str, Any],
    bucket_name: str = "visuals",
) -> int:
    """Delete all files matching metadata criteria.

    Args:
        metadata_filter: MongoDB query for metadata fields.
                        Example: {"asset_id": "abc123"} deletes all variants.
        bucket_name: GridFS bucket name (default: "visuals").

    Returns:
        Number of files deleted.
    """
    bucket = await get_gridfs_bucket(bucket_name)
    db = bucket._collection.database

    # Find all matching files
    files_collection = db[f"{bucket_name}.files"]
    cursor = files_collection.find(
        {f"metadata.{k}": v for k, v in metadata_filter.items()},
        {"_id": 1},
    )

    deleted_count = 0
    async for doc in cursor:
        try:
            await bucket.delete(doc["_id"])
            deleted_count += 1
        except Exception as e:
            logger.error(f"Error deleting file {doc['_id']}: {e}")

    logger.info(f"Deleted {deleted_count} files matching {metadata_filter}")
    return deleted_count


async def file_exists(
    file_id: str,
    bucket_name: str = "visuals",
) -> bool:
    """Check if a file exists in GridFS.

    Args:
        file_id: GridFS file ID (string).
        bucket_name: GridFS bucket name (default: "visuals").

    Returns:
        True if file exists, False otherwise.
    """
    bucket = await get_gridfs_bucket(bucket_name)
    db = bucket._collection.database

    files_collection = db[f"{bucket_name}.files"]
    try:
        count = await files_collection.count_documents({"_id": ObjectId(file_id)})
        return count > 0
    except Exception:
        return False
