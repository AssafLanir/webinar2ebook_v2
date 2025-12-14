"""File service for handling file uploads, downloads, and management."""

import os
import shutil
import uuid
from pathlib import Path

import aiofiles

from src.api.exceptions import FileNotFoundError, FileTooLargeError, InvalidFileTypeError
from src.models.project import (
    ALLOWED_EXTENSIONS,
    ALLOWED_MIME_TYPES,
    MAX_FILE_SIZE,
    Resource,
    ResourceType,
)

# Default uploads directory (can be overridden via environment variable)
UPLOADS_DIR = Path(os.environ.get("UPLOADS_DIR", "uploads"))


class FileService:
    """Service for file operations: upload, download, delete, and cleanup."""

    def __init__(self, uploads_dir: Path | None = None):
        """Initialize the file service.

        Args:
            uploads_dir: Base directory for file storage. Defaults to 'uploads/'.
        """
        self.uploads_dir = uploads_dir or UPLOADS_DIR

    def _ensure_project_dir(self, project_id: str) -> Path:
        """Ensure the project's upload directory exists.

        Args:
            project_id: The project ID.

        Returns:
            Path to the project's upload directory.
        """
        project_dir = self.uploads_dir / project_id
        project_dir.mkdir(parents=True, exist_ok=True)
        return project_dir

    def _get_file_path(self, project_id: str, file_id: str, filename: str) -> Path:
        """Get the full path for a file.

        Args:
            project_id: The project ID.
            file_id: The unique file ID.
            filename: The original filename.

        Returns:
            Full path to the file.
        """
        # Use file_id prefix to ensure uniqueness
        safe_filename = f"{file_id}_{filename}"
        return self.uploads_dir / project_id / safe_filename

    def validate_file(
        self, content_type: str | None, filename: str, file_size: int
    ) -> None:
        """Validate file against size and type constraints.

        Args:
            content_type: The MIME type of the file.
            filename: The original filename.
            file_size: Size of the file in bytes.

        Raises:
            FileTooLargeError: If file exceeds MAX_FILE_SIZE.
            InvalidFileTypeError: If file type is not allowed.
        """
        # Validate file size
        if file_size > MAX_FILE_SIZE:
            raise FileTooLargeError(file_size, MAX_FILE_SIZE)

        # Validate file extension
        ext = Path(filename).suffix.lower()
        if ext not in ALLOWED_EXTENSIONS:
            raise InvalidFileTypeError(
                ext, list(ALLOWED_EXTENSIONS)
            )

        # Validate MIME type if provided
        if content_type and content_type not in ALLOWED_MIME_TYPES:
            raise InvalidFileTypeError(
                content_type, list(ALLOWED_MIME_TYPES.keys())
            )

    async def upload_file(
        self,
        project_id: str,
        filename: str,
        content: bytes,
        content_type: str | None,
        label: str | None = None,
        resource_order: int = 0,
    ) -> Resource:
        """Upload a file and create a Resource entry.

        Args:
            project_id: The project ID.
            filename: Original filename.
            content: File content as bytes.
            content_type: MIME type of the file.
            label: Display label for the resource (defaults to filename).
            resource_order: Order position in the resources list.

        Returns:
            A Resource object with file metadata.

        Raises:
            FileTooLargeError: If file exceeds size limit.
            InvalidFileTypeError: If file type is not allowed.
        """
        # Validate the file
        self.validate_file(content_type, filename, len(content))

        # Generate unique IDs
        file_id = str(uuid.uuid4())[:8]
        resource_id = str(uuid.uuid4())

        # Ensure project directory exists
        self._ensure_project_dir(project_id)

        # Build file path
        file_path = self._get_file_path(project_id, file_id, filename)
        storage_path = f"{project_id}/{file_id}_{filename}"

        # Write file to disk
        async with aiofiles.open(file_path, "wb") as f:
            await f.write(content)

        # Create and return Resource
        return Resource(
            id=resource_id,
            label=label or filename,
            order=resource_order,
            resourceType=ResourceType.FILE,
            urlOrNote="",
            fileId=file_id,
            fileName=filename,
            fileSize=len(content),
            mimeType=content_type,
            storagePath=storage_path,
        )

    async def get_file_content(
        self, project_id: str, file_id: str, filename: str
    ) -> bytes:
        """Read file content from disk.

        Args:
            project_id: The project ID.
            file_id: The unique file ID.
            filename: The original filename.

        Returns:
            File content as bytes.

        Raises:
            FileNotFoundError: If the file doesn't exist.
        """
        file_path = self._get_file_path(project_id, file_id, filename)

        if not file_path.exists():
            raise FileNotFoundError(file_id, project_id)

        async with aiofiles.open(file_path, "rb") as f:
            return await f.read()

    def get_file_path_for_download(
        self, project_id: str, file_id: str, filename: str
    ) -> Path:
        """Get the file path for downloading (for streaming responses).

        Args:
            project_id: The project ID.
            file_id: The unique file ID.
            filename: The original filename.

        Returns:
            Path to the file.

        Raises:
            FileNotFoundError: If the file doesn't exist.
        """
        file_path = self._get_file_path(project_id, file_id, filename)

        if not file_path.exists():
            raise FileNotFoundError(file_id, project_id)

        return file_path

    async def delete_file(self, project_id: str, file_id: str, filename: str) -> bool:
        """Delete a file from disk.

        Args:
            project_id: The project ID.
            file_id: The unique file ID.
            filename: The original filename.

        Returns:
            True if file was deleted, False if it didn't exist.
        """
        file_path = self._get_file_path(project_id, file_id, filename)

        if file_path.exists():
            file_path.unlink()
            return True

        return False

    def cleanup_project_files(self, project_id: str) -> bool:
        """Delete all files for a project (used when project is deleted).

        Args:
            project_id: The project ID.

        Returns:
            True if directory was removed, False if it didn't exist.
        """
        project_dir = self.uploads_dir / project_id

        if project_dir.exists():
            shutil.rmtree(project_dir)
            return True

        return False

    def get_project_files_size(self, project_id: str) -> int:
        """Get total size of all files for a project.

        Args:
            project_id: The project ID.

        Returns:
            Total size in bytes, 0 if directory doesn't exist.
        """
        project_dir = self.uploads_dir / project_id

        if not project_dir.exists():
            return 0

        total_size = 0
        for file_path in project_dir.iterdir():
            if file_path.is_file():
                total_size += file_path.stat().st_size

        return total_size


# Singleton instance for use across the application
file_service = FileService()
