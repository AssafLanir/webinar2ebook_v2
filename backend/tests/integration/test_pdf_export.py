"""Integration tests for PDF export endpoints.

Tests:
- POST /api/projects/{project_id}/ebook/export
- GET /api/projects/{project_id}/ebook/export/status/{job_id}
- POST /api/projects/{project_id}/ebook/export/cancel/{job_id}
- GET /api/projects/{project_id}/ebook/export/download/{job_id}

Note: These tests use mocked PDF generation since WeasyPrint requires
system dependencies that may not be available in CI environments.
"""

from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from httpx import AsyncClient


@pytest_asyncio.fixture
async def project_with_draft(client: AsyncClient) -> str:
    """Create a project with draft content and return its ID."""
    # Create project
    create_resp = await client.post(
        "/projects",
        json={"name": "Export Test Project", "webinarType": "standard_presentation"},
    )
    assert create_resp.status_code == 201
    project_id = create_resp.json()["data"]["id"]

    # Update with draft content
    update_resp = await client.put(
        f"/projects/{project_id}",
        json={
            "name": "Export Test Project",
            "webinarType": "standard_presentation",
            "draftText": """# Chapter 1: Introduction

This is the introduction chapter.

# Chapter 2: Conclusion

This is the conclusion.
""",
            "finalTitle": "Test Export Ebook",
        },
    )
    assert update_resp.status_code == 200
    return project_id


@pytest_asyncio.fixture
async def project_without_draft(client: AsyncClient) -> str:
    """Create a project without draft content and return its ID."""
    create_resp = await client.post(
        "/projects",
        json={"name": "Empty Project", "webinarType": "standard_presentation"},
    )
    assert create_resp.status_code == 201
    return create_resp.json()["data"]["id"]


class TestExportStartEndpoint:
    """Tests for POST /api/projects/{project_id}/ebook/export."""

    async def test_start_export_creates_job(
        self, client: AsyncClient, project_with_draft: str
    ):
        """Starting export creates a job and returns job_id."""
        # Start export (mock PDF generation to avoid WeasyPrint dependency)
        with patch("src.api.routes.ebook.start_pdf_export") as mock_start:
            mock_start.return_value = "test-job-id-123"

            export_resp = await client.post(
                f"/api/projects/{project_with_draft}/ebook/export",
                json={"format": "pdf"},
            )
            assert export_resp.status_code == 200

            data = export_resp.json()
            assert data["error"] is None
            assert data["data"] is not None
            assert data["data"]["job_id"] == "test-job-id-123"

    async def test_start_export_without_draft_returns_error(
        self, client: AsyncClient, project_without_draft: str
    ):
        """Starting export without draft content returns error."""
        export_resp = await client.post(
            f"/api/projects/{project_without_draft}/ebook/export",
            json={"format": "pdf"},
        )
        assert export_resp.status_code == 200

        data = export_resp.json()
        assert data["data"] is None
        assert data["error"] is not None
        assert data["error"]["code"] == "NO_DRAFT_CONTENT"

    async def test_start_export_nonexistent_project_returns_error(
        self, client: AsyncClient
    ):
        """Starting export for nonexistent project returns error."""
        fake_id = "000000000000000000000000"
        export_resp = await client.post(
            f"/api/projects/{fake_id}/ebook/export",
            json={"format": "pdf"},
        )

        data = export_resp.json()
        assert data["data"] is None
        assert data["error"] is not None
        assert data["error"]["code"] == "PROJECT_NOT_FOUND"


class TestExportStatusEndpoint:
    """Tests for GET /api/projects/{project_id}/ebook/export/status/{job_id}."""

    async def test_get_status_returns_job_info(
        self, client: AsyncClient, project_with_draft: str
    ):
        """Getting status returns job information."""
        from src.models.export_job import ExportJob, ExportJobStatus

        mock_job = ExportJob(
            job_id="test-job-456",
            project_id=project_with_draft,
            status=ExportJobStatus.processing,
            progress=50,
        )

        with patch("src.api.routes.ebook.get_export_job") as mock_get:
            mock_get.return_value = mock_job

            status_resp = await client.get(
                f"/api/projects/{project_with_draft}/ebook/export/status/test-job-456"
            )
            assert status_resp.status_code == 200

            data = status_resp.json()
            assert data["error"] is None
            assert data["data"] is not None
            assert data["data"]["job_id"] == "test-job-456"
            assert data["data"]["status"] == "processing"
            assert data["data"]["progress"] == 50

    async def test_get_status_completed_includes_download_url(
        self, client: AsyncClient, project_with_draft: str
    ):
        """Completed job status includes download URL."""
        from src.models.export_job import ExportJob, ExportJobStatus

        mock_job = ExportJob(
            job_id="test-job-789",
            project_id=project_with_draft,
            status=ExportJobStatus.completed,
            progress=100,
            result_path="/tmp/test.pdf",
        )

        with patch("src.api.routes.ebook.get_export_job") as mock_get:
            mock_get.return_value = mock_job

            status_resp = await client.get(
                f"/api/projects/{project_with_draft}/ebook/export/status/test-job-789"
            )
            assert status_resp.status_code == 200

            data = status_resp.json()
            assert data["data"]["status"] == "completed"
            assert data["data"]["progress"] == 100
            assert data["data"]["download_url"] is not None
            assert "download" in data["data"]["download_url"]

    async def test_get_status_nonexistent_job_returns_error(
        self, client: AsyncClient, project_with_draft: str
    ):
        """Getting status for nonexistent job returns error."""
        with patch("src.api.routes.ebook.get_export_job") as mock_get:
            mock_get.return_value = None

            status_resp = await client.get(
                f"/api/projects/{project_with_draft}/ebook/export/status/nonexistent"
            )
            assert status_resp.status_code == 200

            data = status_resp.json()
            assert data["data"] is None
            assert data["error"] is not None
            assert data["error"]["code"] == "EXPORT_JOB_NOT_FOUND"


class TestExportCancelEndpoint:
    """Tests for POST /api/projects/{project_id}/ebook/export/cancel/{job_id}."""

    async def test_cancel_in_progress_job_succeeds(
        self, client: AsyncClient, project_with_draft: str
    ):
        """Cancelling an in-progress job succeeds."""
        from src.models.export_job import ExportJob, ExportJobStatus

        mock_job = ExportJob(
            job_id="test-cancel-job",
            project_id=project_with_draft,
            status=ExportJobStatus.processing,
            progress=30,
        )

        with patch("src.api.routes.ebook.get_export_job") as mock_get:
            mock_get.return_value = mock_job
            with patch("src.api.routes.ebook.cancel_pdf_export") as mock_cancel:
                mock_cancel.return_value = True

                cancel_resp = await client.post(
                    f"/api/projects/{project_with_draft}/ebook/export/cancel/test-cancel-job"
                )
                assert cancel_resp.status_code == 200

                data = cancel_resp.json()
                assert data["error"] is None
                assert data["data"] is not None
                assert data["data"]["cancelled"] is True

    async def test_cancel_completed_job_returns_error(
        self, client: AsyncClient, project_with_draft: str
    ):
        """Cancelling a completed job returns error."""
        from src.models.export_job import ExportJob, ExportJobStatus

        mock_job = ExportJob(
            job_id="test-completed-job",
            project_id=project_with_draft,
            status=ExportJobStatus.completed,
            progress=100,
        )

        with patch("src.api.routes.ebook.get_export_job") as mock_get:
            mock_get.return_value = mock_job

            cancel_resp = await client.post(
                f"/api/projects/{project_with_draft}/ebook/export/cancel/test-completed-job"
            )
            assert cancel_resp.status_code == 200

            data = cancel_resp.json()
            assert data["data"] is None
            assert data["error"]["code"] == "EXPORT_ALREADY_COMPLETE"


class TestExportDownloadEndpoint:
    """Tests for GET /api/projects/{project_id}/ebook/export/download/{job_id}."""

    async def test_download_nonexistent_job_returns_error(
        self, client: AsyncClient, project_with_draft: str
    ):
        """Downloading nonexistent job returns error."""
        with patch("src.api.routes.ebook.get_export_job") as mock_get:
            mock_get.return_value = None

            download_resp = await client.get(
                f"/api/projects/{project_with_draft}/ebook/export/download/nonexistent"
            )

            data = download_resp.json()
            assert data["data"] is None
            assert data["error"] is not None
            assert data["error"]["code"] == "EXPORT_JOB_NOT_FOUND"

    async def test_download_incomplete_job_returns_error(
        self, client: AsyncClient, project_with_draft: str
    ):
        """Downloading incomplete job returns error."""
        from src.models.export_job import ExportJob, ExportJobStatus

        mock_job = ExportJob(
            job_id="test-incomplete",
            project_id=project_with_draft,
            status=ExportJobStatus.processing,
            progress=50,
        )

        with patch("src.api.routes.ebook.get_export_job") as mock_get:
            mock_get.return_value = mock_job

            download_resp = await client.get(
                f"/api/projects/{project_with_draft}/ebook/export/download/test-incomplete"
            )

            data = download_resp.json()
            assert data["error"] is not None
            assert data["error"]["code"] == "EXPORT_NOT_READY"
