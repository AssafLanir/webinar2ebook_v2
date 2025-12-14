"""Tests for file upload endpoints."""

from pathlib import Path
from typing import Any

import pytest
from httpx import AsyncClient

from src.models.project import MAX_FILE_SIZE
from src.services.file_service import file_service


class TestUploadFile:
    """Tests for POST /projects/{id}/files endpoint."""

    @pytest.mark.asyncio
    async def test_upload_file_success(
        self, client: AsyncClient, sample_project_data: dict[str, Any], tmp_path: Path
    ) -> None:
        """Test successful file upload."""
        # Create a project first
        create_response = await client.post("/projects", json=sample_project_data)
        project = create_response.json()["data"]
        project_id = project["id"]

        # Create a test PDF file
        test_content = b"%PDF-1.4 test content"

        # Upload the file
        response = await client.post(
            f"/projects/{project_id}/files",
            files={"file": ("test.pdf", test_content, "application/pdf")},
            data={"label": "Test Document"},
        )

        assert response.status_code == 201
        json_data = response.json()

        assert json_data["error"] is None
        assert json_data["data"] is not None

        resource = json_data["data"]
        assert resource["label"] == "Test Document"
        assert resource["resourceType"] == "file"
        assert resource["fileName"] == "test.pdf"
        assert resource["fileSize"] == len(test_content)
        assert resource["mimeType"] == "application/pdf"
        assert resource["fileId"] is not None
        assert resource["storagePath"] is not None

        # Cleanup: delete the uploaded file
        file_service.cleanup_project_files(project_id)

    @pytest.mark.asyncio
    async def test_upload_file_default_label(
        self, client: AsyncClient, sample_project_data: dict[str, Any]
    ) -> None:
        """Test file upload uses filename as default label."""
        # Create a project first
        create_response = await client.post("/projects", json=sample_project_data)
        project = create_response.json()["data"]
        project_id = project["id"]

        # Upload without label
        test_content = b"PNG fake content"
        response = await client.post(
            f"/projects/{project_id}/files",
            files={"file": ("my_image.png", test_content, "image/png")},
        )

        assert response.status_code == 201
        json_data = response.json()

        # Label should default to filename
        assert json_data["data"]["label"] == "my_image.png"

        # Cleanup
        file_service.cleanup_project_files(project_id)

    @pytest.mark.asyncio
    async def test_upload_file_project_not_found(self, client: AsyncClient) -> None:
        """Test uploading to non-existent project."""
        test_content = b"test content"
        response = await client.post(
            "/projects/507f1f77bcf86cd799439011/files",
            files={"file": ("test.pdf", test_content, "application/pdf")},
        )

        assert response.status_code == 404
        json_data = response.json()

        assert json_data["data"] is None
        assert json_data["error"]["code"] == "PROJECT_NOT_FOUND"


class TestUploadFileValidation:
    """Tests for file upload validation (size, type)."""

    @pytest.mark.asyncio
    async def test_upload_file_too_large(
        self, client: AsyncClient, sample_project_data: dict[str, Any]
    ) -> None:
        """Test validation error when file exceeds size limit."""
        # Create a project first
        create_response = await client.post("/projects", json=sample_project_data)
        project = create_response.json()["data"]
        project_id = project["id"]

        # Create content larger than MAX_FILE_SIZE (10MB)
        large_content = b"x" * (MAX_FILE_SIZE + 1)

        response = await client.post(
            f"/projects/{project_id}/files",
            files={"file": ("large.pdf", large_content, "application/pdf")},
        )

        assert response.status_code == 400
        json_data = response.json()

        assert json_data["data"] is None
        assert json_data["error"]["code"] == "FILE_TOO_LARGE"

    @pytest.mark.asyncio
    async def test_upload_file_invalid_extension(
        self, client: AsyncClient, sample_project_data: dict[str, Any]
    ) -> None:
        """Test validation error for unsupported file extension."""
        # Create a project first
        create_response = await client.post("/projects", json=sample_project_data)
        project = create_response.json()["data"]
        project_id = project["id"]

        # Try to upload a .exe file
        test_content = b"fake executable content"
        response = await client.post(
            f"/projects/{project_id}/files",
            files={"file": ("malware.exe", test_content, "application/x-msdownload")},
        )

        assert response.status_code == 400
        json_data = response.json()

        assert json_data["data"] is None
        assert json_data["error"]["code"] == "INVALID_FILE_TYPE"

    @pytest.mark.asyncio
    async def test_upload_file_invalid_mime_type(
        self, client: AsyncClient, sample_project_data: dict[str, Any]
    ) -> None:
        """Test validation error for unsupported MIME type."""
        # Create a project first
        create_response = await client.post("/projects", json=sample_project_data)
        project = create_response.json()["data"]
        project_id = project["id"]

        # Try to upload with valid extension but invalid MIME type
        test_content = b"fake content"
        response = await client.post(
            f"/projects/{project_id}/files",
            files={"file": ("script.js", test_content, "application/javascript")},
        )

        assert response.status_code == 400
        json_data = response.json()

        assert json_data["data"] is None
        assert json_data["error"]["code"] == "INVALID_FILE_TYPE"

    @pytest.mark.asyncio
    async def test_upload_allowed_types(
        self, client: AsyncClient, sample_project_data: dict[str, Any]
    ) -> None:
        """Test that all allowed file types can be uploaded."""
        # Create a project first
        create_response = await client.post("/projects", json=sample_project_data)
        project = create_response.json()["data"]
        project_id = project["id"]

        allowed_files = [
            ("test.pdf", "application/pdf"),
            ("test.ppt", "application/vnd.ms-powerpoint"),
            ("test.pptx", "application/vnd.openxmlformats-officedocument.presentationml.presentation"),
            ("test.doc", "application/msword"),
            ("test.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
            ("test.jpg", "image/jpeg"),
            ("test.jpeg", "image/jpeg"),
            ("test.png", "image/png"),
        ]

        for filename, mime_type in allowed_files:
            test_content = b"test content for " + filename.encode()
            response = await client.post(
                f"/projects/{project_id}/files",
                files={"file": (filename, test_content, mime_type)},
            )

            assert response.status_code == 201, f"Failed to upload {filename}"
            json_data = response.json()
            assert json_data["error"] is None, f"Error uploading {filename}: {json_data['error']}"

        # Cleanup
        file_service.cleanup_project_files(project_id)


class TestDownloadFile:
    """Tests for GET /projects/{id}/files/{file_id} endpoint."""

    @pytest.mark.asyncio
    async def test_download_file_success(
        self, client: AsyncClient, sample_project_data: dict[str, Any]
    ) -> None:
        """Test successful file download."""
        # Create a project and upload a file
        create_response = await client.post("/projects", json=sample_project_data)
        project = create_response.json()["data"]
        project_id = project["id"]

        test_content = b"%PDF-1.4 test content for download"
        upload_response = await client.post(
            f"/projects/{project_id}/files",
            files={"file": ("download_test.pdf", test_content, "application/pdf")},
        )
        uploaded_resource = upload_response.json()["data"]
        file_id = uploaded_resource["fileId"]

        # Download the file
        response = await client.get(f"/projects/{project_id}/files/{file_id}")

        assert response.status_code == 200
        assert response.content == test_content
        assert response.headers["content-type"] == "application/pdf"
        assert "download_test.pdf" in response.headers.get("content-disposition", "")

        # Cleanup
        file_service.cleanup_project_files(project_id)

    @pytest.mark.asyncio
    async def test_download_file_not_found(
        self, client: AsyncClient, sample_project_data: dict[str, Any]
    ) -> None:
        """Test downloading non-existent file."""
        # Create a project first
        create_response = await client.post("/projects", json=sample_project_data)
        project = create_response.json()["data"]
        project_id = project["id"]

        response = await client.get(f"/projects/{project_id}/files/nonexistent123")

        assert response.status_code == 404
        json_data = response.json()

        assert json_data["data"] is None
        assert json_data["error"]["code"] == "FILE_NOT_FOUND"

    @pytest.mark.asyncio
    async def test_download_file_project_not_found(self, client: AsyncClient) -> None:
        """Test downloading from non-existent project."""
        response = await client.get("/projects/507f1f77bcf86cd799439011/files/somefile")

        assert response.status_code == 404
        json_data = response.json()

        assert json_data["data"] is None
        assert json_data["error"]["code"] == "PROJECT_NOT_FOUND"


class TestDeleteFile:
    """Tests for DELETE /projects/{id}/files/{file_id} endpoint."""

    @pytest.mark.asyncio
    async def test_delete_file_success(
        self, client: AsyncClient, sample_project_data: dict[str, Any]
    ) -> None:
        """Test successful file deletion."""
        # Create a project and upload a file
        create_response = await client.post("/projects", json=sample_project_data)
        project = create_response.json()["data"]
        project_id = project["id"]

        test_content = b"content to delete"
        upload_response = await client.post(
            f"/projects/{project_id}/files",
            files={"file": ("delete_me.pdf", test_content, "application/pdf")},
        )
        uploaded_resource = upload_response.json()["data"]
        file_id = uploaded_resource["fileId"]

        # Delete the file
        response = await client.delete(f"/projects/{project_id}/files/{file_id}")

        assert response.status_code == 200
        json_data = response.json()

        assert json_data["error"] is None
        assert json_data["data"]["deleted"] is True

        # Verify the file is no longer downloadable
        download_response = await client.get(f"/projects/{project_id}/files/{file_id}")
        assert download_response.status_code == 404

        # Cleanup (should be empty, but just in case)
        file_service.cleanup_project_files(project_id)

    @pytest.mark.asyncio
    async def test_delete_file_not_found(
        self, client: AsyncClient, sample_project_data: dict[str, Any]
    ) -> None:
        """Test deleting non-existent file."""
        # Create a project first
        create_response = await client.post("/projects", json=sample_project_data)
        project = create_response.json()["data"]
        project_id = project["id"]

        response = await client.delete(f"/projects/{project_id}/files/nonexistent123")

        assert response.status_code == 404
        json_data = response.json()

        assert json_data["data"] is None
        assert json_data["error"]["code"] == "FILE_NOT_FOUND"

    @pytest.mark.asyncio
    async def test_delete_file_project_not_found(self, client: AsyncClient) -> None:
        """Test deleting from non-existent project."""
        response = await client.delete("/projects/507f1f77bcf86cd799439011/files/somefile")

        assert response.status_code == 404
        json_data = response.json()

        assert json_data["data"] is None
        assert json_data["error"]["code"] == "PROJECT_NOT_FOUND"


class TestFileCleanupOnProjectDelete:
    """Tests for file cleanup when project is deleted."""

    @pytest.mark.asyncio
    async def test_file_cleanup_on_project_delete(
        self, client: AsyncClient, sample_project_data: dict[str, Any]
    ) -> None:
        """Test that files are cleaned up when project is deleted."""
        # Create a project and upload multiple files
        create_response = await client.post("/projects", json=sample_project_data)
        project = create_response.json()["data"]
        project_id = project["id"]

        # Upload multiple files
        for i in range(3):
            test_content = f"file content {i}".encode()
            await client.post(
                f"/projects/{project_id}/files",
                files={"file": (f"file{i}.pdf", test_content, "application/pdf")},
            )

        # Verify files exist by checking project directory
        project_dir = file_service.uploads_dir / project_id
        assert project_dir.exists()
        assert len(list(project_dir.iterdir())) == 3

        # Delete the project
        delete_response = await client.delete(f"/projects/{project_id}")
        assert delete_response.status_code == 200

        # Verify project directory is cleaned up
        assert not project_dir.exists()

    @pytest.mark.asyncio
    async def test_project_delete_without_files(
        self, client: AsyncClient, sample_project_data: dict[str, Any]
    ) -> None:
        """Test that project without files can still be deleted."""
        # Create a project without uploading files
        create_response = await client.post("/projects", json=sample_project_data)
        project = create_response.json()["data"]
        project_id = project["id"]

        # Delete the project (should not error even without files)
        delete_response = await client.delete(f"/projects/{project_id}")

        assert delete_response.status_code == 200
        json_data = delete_response.json()
        assert json_data["error"] is None
        assert json_data["data"]["deleted"] is True
