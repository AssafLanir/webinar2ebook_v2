"""Integration tests for EPUB export endpoints.

Tests:
- POST /api/projects/{project_id}/ebook/export (format="epub")
- GET /api/projects/{project_id}/ebook/export/status/{job_id}
- POST /api/projects/{project_id}/ebook/export/cancel/{job_id}
- GET /api/projects/{project_id}/ebook/export/download/{job_id}

Header Assertions (per plan.md Integration Test Requirements):
- Content-Type: application/epub+zip
- Content-Disposition: attachment; filename="{safe_title}_{YYYY-MM-DD}.epub"

Note: These tests use mocked EPUB generation since full EPUB generation
requires ebooklib and project content.
"""

import io
import re
import tempfile
import zipfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import AsyncClient

from src.models.export_job import ExportFormat, ExportJob, ExportJobStatus


@pytest_asyncio.fixture
async def project_with_draft_for_epub(client: AsyncClient) -> str:
    """Create a project with draft content for EPUB export and return its ID."""
    # Create project
    create_resp = await client.post(
        "/projects",
        json={"name": "EPUB Export Test Project", "webinarType": "standard_presentation"},
    )
    assert create_resp.status_code == 201
    project_id = create_resp.json()["data"]["id"]

    # Update with draft content
    update_resp = await client.put(
        f"/projects/{project_id}",
        json={
            "name": "EPUB Export Test Project",
            "webinarType": "standard_presentation",
            "draftText": """# Chapter 1: Introduction

This is the introduction chapter for our EPUB test.

# Chapter 2: Main Content

This is the main content chapter.

# Chapter 3: Conclusion

This is the conclusion.
""",
            "finalTitle": "Test EPUB Export Ebook",
            "finalSubtitle": "A Test Subtitle",
            "creditsText": "By Test Author",
        },
    )
    assert update_resp.status_code == 200
    return project_id


def create_mock_epub_file(path: Path) -> None:
    """Create a minimal valid EPUB file for testing."""
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("mimetype", "application/epub+zip")
        zf.writestr("META-INF/container.xml", "<container></container>")
        zf.writestr("content.opf", "<package></package>")


class TestEpubExportStartEndpoint:
    """Tests for POST /api/projects/{project_id}/ebook/export with format=epub."""

    async def test_start_epub_export_creates_job(
        self, client: AsyncClient, project_with_draft_for_epub: str
    ):
        """Starting EPUB export creates a job and returns job_id."""
        export_resp = await client.post(
            f"/api/projects/{project_with_draft_for_epub}/ebook/export?format=epub"
        )
        assert export_resp.status_code == 200

        data = export_resp.json()
        assert data["error"] is None
        assert data["data"] is not None
        assert "job_id" in data["data"]

    async def test_start_epub_export_without_draft_returns_error(
        self, client: AsyncClient
    ):
        """Starting EPUB export without draft content returns error."""
        # Create project without draft
        create_resp = await client.post(
            "/projects",
            json={"name": "Empty EPUB Project", "webinarType": "standard_presentation"},
        )
        project_id = create_resp.json()["data"]["id"]

        export_resp = await client.post(
            f"/api/projects/{project_id}/ebook/export?format=epub"
        )
        assert export_resp.status_code == 200

        data = export_resp.json()
        assert data["data"] is None
        assert data["error"] is not None
        assert data["error"]["code"] == "NO_DRAFT_CONTENT"


class TestEpubExportStatusEndpoint:
    """Tests for EPUB export status polling."""

    async def test_get_epub_status_returns_job_info(
        self, client: AsyncClient, project_with_draft_for_epub: str
    ):
        """Getting EPUB status returns job information."""
        mock_job = ExportJob(
            job_id="epub-test-job-456",
            project_id=project_with_draft_for_epub,
            format=ExportFormat.epub,
            status=ExportJobStatus.processing,
            progress=50,
        )

        with patch("src.api.routes.ebook.get_export_job") as mock_get:
            mock_get.return_value = mock_job

            status_resp = await client.get(
                f"/api/projects/{project_with_draft_for_epub}/ebook/export/status/epub-test-job-456"
            )
            assert status_resp.status_code == 200

            data = status_resp.json()
            assert data["error"] is None
            assert data["data"] is not None
            assert data["data"]["job_id"] == "epub-test-job-456"
            assert data["data"]["status"] == "processing"
            assert data["data"]["progress"] == 50


class TestEpubExportDownloadEndpoint:
    """Tests for GET /api/projects/{project_id}/ebook/export/download/{job_id}.

    These tests verify the EPUB download response headers per plan.md requirements.
    """

    async def test_epub_download_content_type_header(
        self, client: AsyncClient, project_with_draft_for_epub: str, tmp_path: Path
    ):
        """EPUB download must return Content-Type: application/epub+zip."""
        # Create a mock EPUB file
        epub_path = tmp_path / "test-epub-download.epub"
        create_mock_epub_file(epub_path)

        mock_job = ExportJob(
            job_id="epub-download-test",
            project_id=project_with_draft_for_epub,
            format=ExportFormat.epub,
            status=ExportJobStatus.completed,
            progress=100,
            result_path=str(epub_path),
            download_filename="Test_EPUB_2025-12-31.epub",
        )

        with patch("src.api.routes.ebook.get_export_job") as mock_get:
            mock_get.return_value = mock_job
            with patch("src.api.routes.ebook.get_epub_path", return_value=epub_path):
                download_resp = await client.get(
                    f"/api/projects/{project_with_draft_for_epub}/ebook/export/download/epub-download-test"
                )

                # Verify Content-Type header
                assert download_resp.headers["content-type"] == "application/epub+zip"

    async def test_epub_download_content_disposition_header(
        self, client: AsyncClient, project_with_draft_for_epub: str, tmp_path: Path
    ):
        """EPUB download must return Content-Disposition with attachment and .epub filename."""
        # Create a mock EPUB file
        epub_path = tmp_path / "epub-disposition-test.epub"
        create_mock_epub_file(epub_path)

        mock_job = ExportJob(
            job_id="epub-disposition-test",
            project_id=project_with_draft_for_epub,
            format=ExportFormat.epub,
            status=ExportJobStatus.completed,
            progress=100,
            result_path=str(epub_path),
            download_filename="My_Ebook_Title_2025-12-31.epub",
        )

        with patch("src.api.routes.ebook.get_export_job") as mock_get:
            mock_get.return_value = mock_job
            with patch("src.api.routes.ebook.get_epub_path", return_value=epub_path):
                download_resp = await client.get(
                    f"/api/projects/{project_with_draft_for_epub}/ebook/export/download/epub-disposition-test"
                )

                # Verify Content-Disposition header
                content_disp = download_resp.headers.get("content-disposition", "")
                assert "attachment" in content_disp
                assert ".epub" in content_disp

    async def test_epub_download_filename_format(
        self, client: AsyncClient, project_with_draft_for_epub: str, tmp_path: Path
    ):
        """EPUB filename must match pattern: {safe_title}_{YYYY-MM-DD}.epub."""
        # Create a mock EPUB file
        epub_path = tmp_path / "epub-filename-test.epub"
        create_mock_epub_file(epub_path)

        mock_job = ExportJob(
            job_id="epub-filename-test",
            project_id=project_with_draft_for_epub,
            format=ExportFormat.epub,
            status=ExportJobStatus.completed,
            progress=100,
            result_path=str(epub_path),
            download_filename="Test_Title_2025-12-31.epub",
        )

        with patch("src.api.routes.ebook.get_export_job") as mock_get:
            mock_get.return_value = mock_job
            with patch("src.api.routes.ebook.get_epub_path", return_value=epub_path):
                download_resp = await client.get(
                    f"/api/projects/{project_with_draft_for_epub}/ebook/export/download/epub-filename-test"
                )

                content_disp = download_resp.headers.get("content-disposition", "")
                # Verify filename format: {safe_title}_{YYYY-MM-DD}.epub
                filename_pattern = r'filename="[^"]+_\d{4}-\d{2}-\d{2}\.epub"'
                assert re.search(filename_pattern, content_disp), \
                    f"Content-Disposition header does not match expected filename pattern. Got: {content_disp}"

    async def test_epub_download_incomplete_job_returns_error(
        self, client: AsyncClient, project_with_draft_for_epub: str
    ):
        """Downloading incomplete EPUB job returns error."""
        mock_job = ExportJob(
            job_id="epub-incomplete-test",
            project_id=project_with_draft_for_epub,
            format=ExportFormat.epub,
            status=ExportJobStatus.processing,
            progress=50,
        )

        with patch("src.api.routes.ebook.get_export_job") as mock_get:
            mock_get.return_value = mock_job

            download_resp = await client.get(
                f"/api/projects/{project_with_draft_for_epub}/ebook/export/download/epub-incomplete-test"
            )

            data = download_resp.json()
            assert data["error"] is not None
            assert data["error"]["code"] == "EXPORT_NOT_READY"


class TestEpubExportCancelEndpoint:
    """Tests for EPUB export cancellation."""

    async def test_cancel_epub_export_succeeds(
        self, client: AsyncClient, project_with_draft_for_epub: str
    ):
        """Cancelling an in-progress EPUB export succeeds."""
        mock_job = ExportJob(
            job_id="epub-cancel-test",
            project_id=project_with_draft_for_epub,
            format=ExportFormat.epub,
            status=ExportJobStatus.processing,
            progress=30,
        )

        with patch("src.api.routes.ebook.get_export_job") as mock_get:
            mock_get.return_value = mock_job
            with patch("src.api.routes.ebook.cancel_epub_export") as mock_cancel:
                mock_cancel.return_value = True

                cancel_resp = await client.post(
                    f"/api/projects/{project_with_draft_for_epub}/ebook/export/cancel/epub-cancel-test"
                )
                assert cancel_resp.status_code == 200

                data = cancel_resp.json()
                assert data["error"] is None
                assert data["data"] is not None
                assert data["data"]["cancelled"] is True
