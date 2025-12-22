"""Unit tests for draft generation API endpoints.

Tests cover:
- POST /api/ai/draft/generate - start generation
- GET /api/ai/draft/status/{job_id} - poll status
- POST /api/ai/draft/cancel/{job_id} - cancel generation
- POST /api/ai/draft/regenerate - regenerate section

All responses use { data, error } envelope pattern.
"""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from src.api.main import app
from src.models import (
    JobStatus,
    DraftStatusData,
    DraftCancelData,
    DraftPlan,
    ChapterPlan,
    GenerationMetadata,
    VisualPlan,
    TranscriptSegment,
    GenerationProgress,
)
from src.services.job_store import InMemoryJobStore, set_job_store


# Use in-memory store for tests
@pytest.fixture(autouse=True)
def reset_job_store():
    """Reset job store to in-memory for tests."""
    store = InMemoryJobStore()
    set_job_store(store)
    yield store
    set_job_store(None)


client = TestClient(app)


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def sample_transcript():
    """Sample transcript (>500 chars)."""
    return "A" * 600  # Simple valid transcript


@pytest.fixture
def sample_outline():
    """Sample outline (>=3 items)."""
    return [
        {"id": "1", "title": "Intro", "level": 1},
        {"id": "2", "title": "Main", "level": 1},
        {"id": "3", "title": "Conclusion", "level": 1},
    ]


@pytest.fixture
def sample_style_config():
    """Sample style config."""
    return {
        "version": 1,
        "preset_id": "default_webinar_ebook_v1",
        "style": {"tone": "conversational"},
    }


@pytest.fixture
def sample_draft_plan():
    """Sample DraftPlan for mocking."""
    return DraftPlan(
        version=1,
        book_title="Test Book",
        chapters=[
            ChapterPlan(
                chapter_number=1,
                title="Introduction",
                outline_item_id="1",
                goals=["Learn basics"],
                key_points=["Point 1"],
                transcript_segments=[TranscriptSegment(start_char=0, end_char=100)],
                estimated_words=500,
            ),
        ],
        visual_plan=VisualPlan(opportunities=[], assets=[]),
        generation_metadata=GenerationMetadata(
            estimated_total_words=500,
            estimated_generation_time_seconds=15,
            transcript_utilization=0.8,
        ),
    )


# =============================================================================
# Generate Endpoint Tests
# =============================================================================

class TestGenerateEndpoint:
    """Tests for POST /api/ai/draft/generate."""

    def test_generate_returns_job_id(
        self, sample_transcript, sample_outline, sample_style_config
    ):
        """Test that generate returns job_id and queued status."""
        with patch("src.services.draft_service.start_generation", new_callable=AsyncMock) as mock:
            mock.return_value = "test-job-123"

            response = client.post(
                "/api/ai/draft/generate",
                json={
                    "transcript": sample_transcript,
                    "outline": sample_outline,
                    "style_config": sample_style_config,
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert data["error"] is None
        assert data["data"]["job_id"] == "test-job-123"
        assert data["data"]["status"] == "queued"

    def test_generate_validates_transcript_length(
        self, sample_outline, sample_style_config
    ):
        """Test that transcript < 500 chars returns error."""
        response = client.post(
            "/api/ai/draft/generate",
            json={
                "transcript": "short",  # < 500 chars
                "outline": sample_outline,
                "style_config": sample_style_config,
            },
        )

        assert response.status_code == 400
        data = response.json()
        assert data["data"] is None
        assert data["error"]["code"] == "TRANSCRIPT_TOO_SHORT"

    def test_generate_validates_outline_length(
        self, sample_transcript, sample_style_config
    ):
        """Test that outline < 3 items returns error."""
        response = client.post(
            "/api/ai/draft/generate",
            json={
                "transcript": sample_transcript,
                "outline": [{"id": "1", "title": "Only One", "level": 1}],  # < 3
                "style_config": sample_style_config,
            },
        )

        assert response.status_code == 400
        data = response.json()
        assert data["data"] is None
        assert data["error"]["code"] == "OUTLINE_TOO_SMALL"

    def test_generate_response_envelope_format(
        self, sample_transcript, sample_outline, sample_style_config
    ):
        """Test that response follows { data, error } envelope."""
        with patch("src.services.draft_service.start_generation", new_callable=AsyncMock) as mock:
            mock.return_value = "job-123"

            response = client.post(
                "/api/ai/draft/generate",
                json={
                    "transcript": sample_transcript,
                    "outline": sample_outline,
                    "style_config": sample_style_config,
                },
            )

        data = response.json()
        assert "data" in data
        assert "error" in data


# =============================================================================
# Status Endpoint Tests
# =============================================================================

class TestStatusEndpoint:
    """Tests for GET /api/ai/draft/status/{job_id}."""

    def test_status_returns_job_info(self):
        """Test that status returns job information."""
        status_data = DraftStatusData(
            job_id="job-123",
            status=JobStatus.generating,
            progress=GenerationProgress(
                current_chapter=2,
                total_chapters=5,
                chapters_completed=1,
            ),
        )

        with patch("src.services.draft_service.get_job_status", new_callable=AsyncMock) as mock:
            mock.return_value = status_data

            response = client.get("/api/ai/draft/status/job-123")

        assert response.status_code == 200
        data = response.json()
        assert data["error"] is None
        assert data["data"]["job_id"] == "job-123"
        assert data["data"]["status"] == "generating"
        assert data["data"]["progress"]["current_chapter"] == 2

    def test_status_not_found(self):
        """Test that unknown job returns 404."""
        with patch("src.services.draft_service.get_job_status", new_callable=AsyncMock) as mock:
            mock.return_value = None

            response = client.get("/api/ai/draft/status/unknown-job")

        assert response.status_code == 404
        data = response.json()
        assert data["data"] is None
        assert data["error"]["code"] == "JOB_NOT_FOUND"

    def test_status_completed_includes_draft(self, sample_draft_plan):
        """Test that completed status includes draft markdown."""
        status_data = DraftStatusData(
            job_id="job-123",
            status=JobStatus.completed,
            draft_markdown="# Test Book\n\n## Chapter 1\n\nContent",
            draft_plan=sample_draft_plan,
            visual_plan=sample_draft_plan.visual_plan,
        )

        with patch("src.services.draft_service.get_job_status", new_callable=AsyncMock) as mock:
            mock.return_value = status_data

            response = client.get("/api/ai/draft/status/job-123")

        assert response.status_code == 200
        data = response.json()
        assert data["data"]["status"] == "completed"
        assert data["data"]["draft_markdown"] is not None
        assert data["data"]["draft_plan"] is not None

    def test_status_cancelled_includes_partial(self):
        """Test that cancelled status includes partial results."""
        status_data = DraftStatusData(
            job_id="job-123",
            status=JobStatus.cancelled,
            partial_draft_markdown="# Partial\n\n## Ch1\n\nContent",
            chapters_available=1,
        )

        with patch("src.services.draft_service.get_job_status", new_callable=AsyncMock) as mock:
            mock.return_value = status_data

            response = client.get("/api/ai/draft/status/job-123")

        assert response.status_code == 200
        data = response.json()
        assert data["data"]["status"] == "cancelled"
        assert data["data"]["partial_draft_markdown"] is not None
        assert data["data"]["chapters_available"] == 1


# =============================================================================
# Cancel Endpoint Tests
# =============================================================================

class TestCancelEndpoint:
    """Tests for POST /api/ai/draft/cancel/{job_id}."""

    def test_cancel_sets_flag(self):
        """Test that cancel returns success."""
        cancel_data = DraftCancelData(
            job_id="job-123",
            status=JobStatus.generating,
            cancelled=True,
            message="Cancellation requested",
        )

        with patch("src.services.draft_service.cancel_job", new_callable=AsyncMock) as mock:
            mock.return_value = cancel_data

            response = client.post("/api/ai/draft/cancel/job-123")

        assert response.status_code == 200
        data = response.json()
        assert data["error"] is None
        assert data["data"]["cancelled"] is True

    def test_cancel_not_found(self):
        """Test that unknown job returns 404."""
        with patch("src.services.draft_service.cancel_job", new_callable=AsyncMock) as mock:
            mock.return_value = None

            response = client.post("/api/ai/draft/cancel/unknown-job")

        assert response.status_code == 404
        data = response.json()
        assert data["data"] is None
        assert data["error"]["code"] == "JOB_NOT_FOUND"

    def test_cancel_already_completed(self):
        """Test cancelling already completed job."""
        cancel_data = DraftCancelData(
            job_id="job-123",
            status=JobStatus.completed,
            cancelled=False,
            message="Job already in terminal state: completed",
        )

        with patch("src.services.draft_service.cancel_job", new_callable=AsyncMock) as mock:
            mock.return_value = cancel_data

            response = client.post("/api/ai/draft/cancel/job-123")

        assert response.status_code == 200
        data = response.json()
        assert data["data"]["cancelled"] is False


# =============================================================================
# Regenerate Endpoint Tests
# =============================================================================

class TestRegenerateEndpoint:
    """Tests for POST /api/ai/draft/regenerate."""

    def test_regenerate_section_not_found(self, sample_draft_plan):
        """Test that unknown section returns error."""
        with patch("src.services.draft_service.regenerate_section", new_callable=AsyncMock) as mock:
            mock.return_value = None

            response = client.post(
                "/api/ai/draft/regenerate",
                json={
                    "section_outline_item_id": "unknown",
                    "draft_plan": sample_draft_plan.model_dump(),
                    "existing_draft": "# Draft\n\nContent",
                    "style_config": {"version": 1, "style": {}},
                },
            )

        assert response.status_code == 400
        data = response.json()
        assert data["error"]["code"] == "SECTION_NOT_FOUND"


# =============================================================================
# Envelope Pattern Tests
# =============================================================================

class TestEnvelopePattern:
    """Tests for consistent { data, error } envelope."""

    def test_success_response_has_null_error(
        self, sample_transcript, sample_outline, sample_style_config
    ):
        """Test that success responses have null error."""
        with patch("src.services.draft_service.start_generation", new_callable=AsyncMock) as mock:
            mock.return_value = "job-123"

            response = client.post(
                "/api/ai/draft/generate",
                json={
                    "transcript": sample_transcript,
                    "outline": sample_outline,
                    "style_config": sample_style_config,
                },
            )

        data = response.json()
        assert data["error"] is None
        assert data["data"] is not None

    def test_error_response_has_null_data(self, sample_outline, sample_style_config):
        """Test that error responses have null data."""
        response = client.post(
            "/api/ai/draft/generate",
            json={
                "transcript": "short",
                "outline": sample_outline,
                "style_config": sample_style_config,
            },
        )

        data = response.json()
        assert data["data"] is None
        assert data["error"] is not None
        assert "code" in data["error"]
        assert "message" in data["error"]
