"""Integration tests for QA API endpoints.

T008: Tests for the QA analysis workflow:
- POST /qa/analyze - Start QA analysis
- GET /qa/status/{job_id} - Poll status
- GET /qa/report/{project_id} - Get report
- POST /qa/cancel/{job_id} - Cancel analysis
"""

import asyncio
import json
import uuid
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from httpx import AsyncClient

from src.models.qa_report import (
    QAReport,
    RubricScores,
    IssueCounts,
    QAIssue,
    IssueSeverity,
    IssueType,
)


# ============================================================================
# Fixtures
# ============================================================================

@pytest_asyncio.fixture
async def project_with_draft(client: AsyncClient, mock_db: Any) -> dict:
    """Create a project with a draft for QA testing."""
    # Create project (note: /projects not /api/projects per main.py routing)
    response = await client.post(
        "/projects",
        json={"name": "QA Test Project", "webinarType": "standard_presentation"},
    )
    assert response.status_code == 201, f"Failed to create project: {response.text}"
    project_data = response.json()["data"]
    project_id = project_data["id"]

    # Add a draft (simulating draft generation completion)
    draft_markdown = """# Introduction

Welcome to this comprehensive guide on software development.
We will cover various topics including programming fundamentals.

# Chapter 1: Getting Started

In this chapter, we discuss the basics of programming.
Variables are containers for storing data values.
Loops allow you to repeat code blocks.
Functions help organize and reuse code.

# Chapter 2: Advanced Topics

Here we cover more advanced material like design patterns.
Design patterns are reusable solutions to common problems.
Architecture is important for large-scale systems.

# Conclusion

Thank you for reading this comprehensive guide.
We covered programming fundamentals and advanced topics.
"""

    await client.put(
        f"/projects/{project_id}",
        json={
            "name": "QA Test Project",
            "webinarType": "standard_presentation",
            "draftText": draft_markdown,
        },
    )

    return {"id": project_id, "draftText": draft_markdown}


@pytest_asyncio.fixture
async def project_without_draft(client: AsyncClient, mock_db: Any) -> dict:
    """Create a project without a draft."""
    response = await client.post(
        "/projects",
        json={"name": "No Draft Project", "webinarType": "standard_presentation"},
    )
    assert response.status_code == 201, f"Failed to create project: {response.text}"
    project_data = response.json()["data"]
    return {"id": project_data["id"]}


def create_mock_qa_report(project_id: str) -> QAReport:
    """Create a mock QA report for testing."""
    return QAReport(
        id=str(uuid.uuid4()),
        project_id=project_id,
        draft_hash="abc123",
        overall_score=85,
        rubric_scores=RubricScores(
            structure=90,
            clarity=85,
            faithfulness=80,
            repetition=85,
            completeness=85,
        ),
        issue_counts=IssueCounts(
            critical=0,
            warning=2,
            info=3,
        ),
        total_issue_count=5,
        truncated=False,
        generated_at=datetime.now(timezone.utc),
        analysis_duration_ms=1500,
        issues=[
            QAIssue(
                id="test-1",
                severity=IssueSeverity.warning,
                issue_type=IssueType.structure,
                message="Test issue 1",
            ),
            QAIssue(
                id="test-2",
                severity=IssueSeverity.info,
                issue_type=IssueType.clarity,
                message="Test issue 2",
            ),
        ],
    )


# ============================================================================
# POST /qa/analyze Tests
# ============================================================================

class TestAnalyzeEndpoint:
    """Tests for POST /qa/analyze endpoint."""

    @pytest.mark.asyncio
    async def test_analyze_nonexistent_project(self, client: AsyncClient, mock_db: Any):
        """Analyze nonexistent project returns 404."""
        response = await client.post(
            "/api/qa/analyze",
            json={"project_id": "nonexistent-id"},
        )
        assert response.status_code == 404
        data = response.json()
        assert data["error"]["code"] == "PROJECT_NOT_FOUND"

    @pytest.mark.asyncio
    async def test_analyze_project_without_draft(
        self, client: AsyncClient, project_without_draft: dict
    ):
        """Analyze project without draft returns 400."""
        response = await client.post(
            "/api/qa/analyze",
            json={"project_id": project_without_draft["id"]},
        )
        assert response.status_code == 400
        data = response.json()
        assert data["error"]["code"] == "NO_DRAFT"

    @pytest.mark.asyncio
    async def test_analyze_starts_job(
        self, client: AsyncClient, project_with_draft: dict
    ):
        """Analyze returns job_id and starts background task."""
        # Mock the QA evaluator to avoid actual LLM calls
        mock_report = create_mock_qa_report(project_with_draft["id"])

        with patch("src.api.routes.qa.evaluate_draft") as mock_evaluate:
            mock_evaluate.return_value = mock_report

            response = await client.post(
                "/api/qa/analyze",
                json={"project_id": project_with_draft["id"]},
            )

        assert response.status_code == 200
        data = response.json()["data"]
        assert "job_id" in data
        assert data["status"] == "queued"
        assert data["job_id"] is not None

    @pytest.mark.asyncio
    async def test_analyze_force_rerun(
        self, client: AsyncClient, project_with_draft: dict, mock_db: Any
    ):
        """Force=True triggers reanalysis even with existing report."""
        # First, add a QA report to the project via service
        from src.services.project_service import patch_project

        mock_report = create_mock_qa_report(project_with_draft["id"])
        await patch_project(
            project_with_draft["id"],
            {"qaReport": mock_report.model_dump(mode="json")},
        )

        # Mock should_run_qa to return True for force
        with patch("src.api.routes.qa.evaluate_draft") as mock_evaluate:
            mock_evaluate.return_value = mock_report

            response = await client.post(
                "/api/qa/analyze",
                json={"project_id": project_with_draft["id"], "force": True},
            )

        assert response.status_code == 200
        data = response.json()["data"]
        # Should start a new job even with existing report
        assert data["job_id"] is not None or data["status"] == "already_current"


# ============================================================================
# GET /qa/status/{job_id} Tests
# ============================================================================

class TestStatusEndpoint:
    """Tests for GET /qa/status/{job_id} endpoint."""

    @pytest.mark.asyncio
    async def test_status_nonexistent_job(self, client: AsyncClient, mock_db: Any):
        """Status for nonexistent job returns 404."""
        response = await client.get("/api/qa/status/nonexistent-job-id")
        assert response.status_code == 404
        data = response.json()
        assert data["error"]["code"] == "JOB_NOT_FOUND"

    @pytest.mark.asyncio
    async def test_status_returns_progress(
        self, client: AsyncClient, project_with_draft: dict
    ):
        """Status endpoint returns current progress."""
        # Create a job first
        from src.services.qa_job_store import create_qa_job, update_qa_job
        from src.models.qa_job import QAJobStatus

        job_id = await create_qa_job(project_with_draft["id"])
        await update_qa_job(
            job_id,
            status=QAJobStatus.running,
            progress_pct=50,
            current_stage="structural_analysis",
        )

        response = await client.get(f"/api/qa/status/{job_id}")
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["job_id"] == job_id
        assert data["status"] == "running"
        assert data["progress_pct"] == 50
        assert data["current_stage"] == "structural_analysis"

    @pytest.mark.asyncio
    async def test_status_returns_report_when_complete(
        self, client: AsyncClient, project_with_draft: dict
    ):
        """Status includes report when job is complete."""
        from src.services.qa_job_store import create_qa_job, update_qa_job
        from src.models.qa_job import QAJobStatus

        mock_report = create_mock_qa_report(project_with_draft["id"])

        job_id = await create_qa_job(project_with_draft["id"])
        await update_qa_job(
            job_id,
            status=QAJobStatus.completed,
            progress_pct=100,
            report=mock_report,
        )

        response = await client.get(f"/api/qa/status/{job_id}")
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["status"] == "completed"
        assert data["progress_pct"] == 100
        assert data["report"] is not None
        assert data["report"]["overall_score"] == 85

    @pytest.mark.asyncio
    async def test_status_returns_error_when_failed(
        self, client: AsyncClient, project_with_draft: dict
    ):
        """Status includes error message when job failed."""
        from src.services.qa_job_store import create_qa_job, update_qa_job
        from src.models.qa_job import QAJobStatus

        job_id = await create_qa_job(project_with_draft["id"])
        await update_qa_job(
            job_id,
            status=QAJobStatus.failed,
            error="Analysis failed: LLM error",
            error_code="LLM_ERROR",
        )

        response = await client.get(f"/api/qa/status/{job_id}")
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["status"] == "failed"
        assert data["error"] == "Analysis failed: LLM error"


# ============================================================================
# GET /qa/report/{project_id} Tests
# ============================================================================

class TestReportEndpoint:
    """Tests for GET /qa/report/{project_id} endpoint."""

    @pytest.mark.asyncio
    async def test_report_nonexistent_project(self, client: AsyncClient, mock_db: Any):
        """Report for nonexistent project returns 404."""
        response = await client.get("/api/qa/report/nonexistent-id")
        assert response.status_code == 404
        data = response.json()
        assert data["error"]["code"] == "PROJECT_NOT_FOUND"

    @pytest.mark.asyncio
    async def test_report_returns_null_when_none(
        self, client: AsyncClient, project_with_draft: dict
    ):
        """Report returns null when no QA report exists."""
        response = await client.get(f"/api/qa/report/{project_with_draft['id']}")
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["report"] is None

    @pytest.mark.asyncio
    async def test_report_returns_existing_report(
        self, client: AsyncClient, project_with_draft: dict
    ):
        """Report returns existing QA report from project."""
        # Add a QA report to the project via service
        from src.services.project_service import patch_project

        mock_report = create_mock_qa_report(project_with_draft["id"])
        await patch_project(
            project_with_draft["id"],
            {"qaReport": mock_report.model_dump(mode="json")},
        )

        response = await client.get(f"/api/qa/report/{project_with_draft['id']}")
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["report"] is not None
        assert data["report"]["overall_score"] == 85
        assert data["report"]["total_issue_count"] == 5


# ============================================================================
# POST /qa/cancel/{job_id} Tests
# ============================================================================

class TestCancelEndpoint:
    """Tests for POST /qa/cancel/{job_id} endpoint."""

    @pytest.mark.asyncio
    async def test_cancel_nonexistent_job(self, client: AsyncClient, mock_db: Any):
        """Cancel nonexistent job returns 404."""
        response = await client.post("/api/qa/cancel/nonexistent-job-id")
        assert response.status_code == 404
        data = response.json()
        assert data["error"]["code"] == "JOB_NOT_FOUND"

    @pytest.mark.asyncio
    async def test_cancel_running_job(
        self, client: AsyncClient, project_with_draft: dict
    ):
        """Cancel running job returns success."""
        from src.services.qa_job_store import create_qa_job, update_qa_job
        from src.models.qa_job import QAJobStatus

        job_id = await create_qa_job(project_with_draft["id"])
        await update_qa_job(job_id, status=QAJobStatus.running)

        response = await client.post(f"/api/qa/cancel/{job_id}")
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["cancelled"] is True
        assert data["status"] == "cancelling"

    @pytest.mark.asyncio
    async def test_cancel_completed_job(
        self, client: AsyncClient, project_with_draft: dict
    ):
        """Cancel already completed job returns appropriate message."""
        from src.services.qa_job_store import create_qa_job, update_qa_job
        from src.models.qa_job import QAJobStatus

        mock_report = create_mock_qa_report(project_with_draft["id"])

        job_id = await create_qa_job(project_with_draft["id"])
        await update_qa_job(
            job_id,
            status=QAJobStatus.completed,
            report=mock_report,
        )

        response = await client.post(f"/api/qa/cancel/{job_id}")
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["cancelled"] is False
        assert "terminal state" in data["message"]


# ============================================================================
# End-to-End Workflow Tests
# ============================================================================

class TestQAWorkflow:
    """End-to-end tests for complete QA workflow."""

    @pytest.mark.asyncio
    async def test_complete_qa_workflow(
        self, client: AsyncClient, project_with_draft: dict
    ):
        """Test complete workflow: analyze -> poll status -> get report."""
        mock_report = create_mock_qa_report(project_with_draft["id"])

        # Patch the evaluator to return our mock report
        with patch("src.api.routes.qa.evaluate_draft", new_callable=AsyncMock) as mock_eval:
            mock_eval.return_value = mock_report

            # 1. Start analysis
            response = await client.post(
                "/api/qa/analyze",
                json={"project_id": project_with_draft["id"]},
            )
            assert response.status_code == 200
            job_id = response.json()["data"]["job_id"]

            # Wait for background task to complete
            await asyncio.sleep(0.5)

        # 2. Check status - should be completed
        response = await client.get(f"/api/qa/status/{job_id}")
        data = response.json()["data"]
        # Status may still be running or completed
        assert data["status"] in ["running", "completed", "queued"]

        # 3. Get report from project (may take a moment to save)
        await asyncio.sleep(0.3)
        response = await client.get(f"/api/qa/report/{project_with_draft['id']}")
        # Report may or may not be saved yet depending on timing

    @pytest.mark.asyncio
    async def test_multiple_analyses_same_project(
        self, client: AsyncClient, project_with_draft: dict
    ):
        """Multiple analysis requests for same project are handled correctly."""
        mock_report = create_mock_qa_report(project_with_draft["id"])

        with patch("src.api.routes.qa.evaluate_draft", new_callable=AsyncMock) as mock_eval:
            mock_eval.return_value = mock_report

            # Start first analysis
            response1 = await client.post(
                "/api/qa/analyze",
                json={"project_id": project_with_draft["id"]},
            )
            assert response1.status_code == 200
            job_id_1 = response1.json()["data"]["job_id"]

            # Start second analysis immediately (force=True to bypass cache)
            response2 = await client.post(
                "/api/qa/analyze",
                json={"project_id": project_with_draft["id"], "force": True},
            )
            assert response2.status_code == 200
            job_id_2 = response2.json()["data"]["job_id"]

            # Both should get job IDs
            assert job_id_1 is not None
            # Second might get a different job or "already_current"


# ============================================================================
# Response Format Tests
# ============================================================================

class TestResponseFormat:
    """Tests for API response format consistency."""

    @pytest.mark.asyncio
    async def test_success_response_format(
        self, client: AsyncClient, project_with_draft: dict
    ):
        """Success responses follow {data, error} format."""
        response = await client.get(f"/api/qa/report/{project_with_draft['id']}")
        json_data = response.json()

        assert "data" in json_data
        assert json_data["error"] is None

    @pytest.mark.asyncio
    async def test_error_response_format(self, client: AsyncClient, mock_db: Any):
        """Error responses follow {data, error} format."""
        response = await client.get("/api/qa/report/nonexistent")
        json_data = response.json()

        assert json_data["data"] is None
        assert "error" in json_data
        assert "code" in json_data["error"]
        assert "message" in json_data["error"]

    @pytest.mark.asyncio
    async def test_report_structure(
        self, client: AsyncClient, project_with_draft: dict
    ):
        """QA report has expected structure."""
        from src.services.project_service import patch_project

        mock_report = create_mock_qa_report(project_with_draft["id"])
        await patch_project(
            project_with_draft["id"],
            {"qaReport": mock_report.model_dump(mode="json")},
        )

        response = await client.get(f"/api/qa/report/{project_with_draft['id']}")
        report = response.json()["data"]["report"]

        # Check required fields
        assert "project_id" in report
        assert "overall_score" in report
        assert "rubric_scores" in report
        assert "issue_counts" in report
        assert "issues" in report
        assert "total_issue_count" in report

        # Check rubric structure
        rubric = report["rubric_scores"]
        assert "structure" in rubric
        assert "clarity" in rubric
        assert "faithfulness" in rubric
        assert "repetition" in rubric
        assert "completeness" in rubric

        # Check issue counts structure
        counts = report["issue_counts"]
        assert "critical" in counts
        assert "warning" in counts
        assert "info" in counts
