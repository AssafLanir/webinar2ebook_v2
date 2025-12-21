"""Integration tests for draft generation flow.

Tests the complete draft generation workflow:
1. POST /api/ai/draft/generate - Start generation
2. GET /api/ai/draft/status/:job_id - Poll for progress
3. POST /api/ai/draft/cancel/:job_id - Cancel generation

Verifies:
- Job lifecycle (queued -> planning -> generating -> completed)
- Progress updates with partial drafts
- Cancellation preserves partial results
- { data, error } envelope consistency
"""

import asyncio
from unittest.mock import patch, AsyncMock

import pytest
from httpx import AsyncClient, ASGITransport

from src.api.main import app
from src.services.job_store import get_job_store, JobStore
from src.services.draft_service import get_job_status
from src.models import JobStatus


@pytest.fixture
def mock_llm_client():
    """Mock LLM client to avoid actual API calls."""
    with patch("src.services.draft_service.LLMClient") as mock:
        mock_instance = AsyncMock()
        mock.return_value = mock_instance

        # Mock generate to return valid JSON for DraftPlan
        mock_instance.generate = AsyncMock(return_value=AsyncMock(
            content='{"version": 1, "book_title": "Test Book", "chapters": [{"chapter_number": 1, "title": "Chapter 1", "outline_item_id": "item-1", "goals": ["Goal 1"], "key_points": ["Point 1"], "transcript_segments": [{"start_char": 0, "end_char": 100, "relevance": "primary"}], "estimated_words": 500}], "visual_plan": {"opportunities": [], "suggested_assets": []}, "generation_metadata": {"estimated_total_words": 500, "estimated_generation_time_seconds": 30, "transcript_utilization": 0.8}}'
        ))

        yield mock_instance


@pytest.fixture
async def reset_job_store():
    """Reset the job store before and after each test."""
    store = get_job_store()
    # Clear all jobs
    store._jobs.clear()
    yield store
    store._jobs.clear()


@pytest.fixture
async def client():
    """Async HTTP client for testing."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


class TestDraftGenerationFlow:
    """Tests for the complete draft generation workflow."""

    @pytest.mark.asyncio
    async def test_generate_returns_job_id_and_queued_status(
        self, client: AsyncClient, reset_job_store, mock_llm_client
    ):
        """POST /generate should return job_id with queued status."""
        response = await client.post(
            "/api/ai/draft/generate",
            json={
                "transcript": "A" * 600,  # Exceeds 500 char minimum
                "outline": [
                    {"id": "item-1", "title": "Introduction", "level": 1, "order": 0},
                    {"id": "item-2", "title": "Main Content", "level": 1, "order": 1},
                    {"id": "item-3", "title": "Conclusion", "level": 1, "order": 2},
                ],
                "resources": [],
                "style_config": {"version": 1, "preset_id": "test", "style": {}},
            },
        )

        assert response.status_code == 200
        data = response.json()

        # Check envelope structure
        assert "data" in data
        assert "error" in data
        assert data["error"] is None

        # Check response data
        assert data["data"]["job_id"] is not None
        assert data["data"]["status"] in ["queued", "planning", "generating"]

    @pytest.mark.asyncio
    async def test_status_returns_progress_during_generation(
        self, client: AsyncClient, reset_job_store, mock_llm_client
    ):
        """GET /status/:job_id should return progress info during generation."""
        # Start generation
        gen_response = await client.post(
            "/api/ai/draft/generate",
            json={
                "transcript": "A" * 600,
                "outline": [
                    {"id": "item-1", "title": "Chapter 1", "level": 1, "order": 0},
                    {"id": "item-2", "title": "Chapter 2", "level": 1, "order": 1},
                    {"id": "item-3", "title": "Chapter 3", "level": 1, "order": 2},
                ],
                "resources": [],
                "style_config": {"version": 1, "preset_id": "test", "style": {}},
            },
        )

        job_id = gen_response.json()["data"]["job_id"]

        # Poll for status
        status_response = await client.get(f"/api/ai/draft/status/{job_id}")

        assert status_response.status_code == 200
        data = status_response.json()

        # Check envelope
        assert "data" in data
        assert "error" in data
        assert data["error"] is None

        # Status should be present
        assert data["data"]["job_id"] == job_id
        assert data["data"]["status"] is not None

    @pytest.mark.asyncio
    async def test_cancel_stops_generation(
        self, client: AsyncClient, reset_job_store, mock_llm_client
    ):
        """POST /cancel/:job_id should request cancellation."""
        # Start generation with slow mock
        mock_llm_client.generate = AsyncMock(side_effect=lambda *args, **kwargs: asyncio.sleep(10))

        gen_response = await client.post(
            "/api/ai/draft/generate",
            json={
                "transcript": "A" * 600,
                "outline": [
                    {"id": "item-1", "title": "Chapter 1", "level": 1, "order": 0},
                    {"id": "item-2", "title": "Chapter 2", "level": 1, "order": 1},
                    {"id": "item-3", "title": "Chapter 3", "level": 1, "order": 2},
                ],
                "resources": [],
                "style_config": {"version": 1, "preset_id": "test", "style": {}},
            },
        )

        job_id = gen_response.json()["data"]["job_id"]

        # Cancel immediately
        cancel_response = await client.post(f"/api/ai/draft/cancel/{job_id}")

        assert cancel_response.status_code == 200
        data = cancel_response.json()

        # Check envelope
        assert "data" in data
        assert "error" in data
        assert data["error"] is None

        # Should indicate cancellation was requested or completed
        assert data["data"]["job_id"] == job_id

    @pytest.mark.asyncio
    async def test_validation_error_returns_400_with_envelope(
        self, client: AsyncClient, reset_job_store
    ):
        """Invalid request should return 400 with proper { data, error } envelope."""
        # Transcript too short
        response = await client.post(
            "/api/ai/draft/generate",
            json={
                "transcript": "Too short",  # Under 500 chars
                "outline": [
                    {"id": "item-1", "title": "Chapter 1", "level": 1, "order": 0},
                    {"id": "item-2", "title": "Chapter 2", "level": 1, "order": 1},
                    {"id": "item-3", "title": "Chapter 3", "level": 1, "order": 2},
                ],
                "resources": [],
                "style_config": {"version": 1, "preset_id": "test", "style": {}},
            },
        )

        assert response.status_code == 400
        data = response.json()

        # Check envelope
        assert "data" in data
        assert "error" in data
        assert data["data"] is None
        assert data["error"] is not None
        assert data["error"]["code"] == "TRANSCRIPT_TOO_SHORT"
        assert "500" in data["error"]["message"]

    @pytest.mark.asyncio
    async def test_not_found_returns_404_with_envelope(
        self, client: AsyncClient, reset_job_store
    ):
        """Non-existent job should return 404 with proper envelope."""
        response = await client.get("/api/ai/draft/status/nonexistent-job-id")

        assert response.status_code == 404
        data = response.json()

        # Check envelope
        assert "data" in data
        assert "error" in data
        assert data["data"] is None
        assert data["error"] is not None
        assert data["error"]["code"] == "JOB_NOT_FOUND"


class TestEnvelopeConsistency:
    """Tests for { data, error } envelope pattern consistency."""

    @pytest.mark.asyncio
    async def test_success_has_null_error(
        self, client: AsyncClient, reset_job_store, mock_llm_client
    ):
        """Successful responses should have error=null."""
        response = await client.post(
            "/api/ai/draft/generate",
            json={
                "transcript": "A" * 600,
                "outline": [
                    {"id": "item-1", "title": "Chapter 1", "level": 1, "order": 0},
                    {"id": "item-2", "title": "Chapter 2", "level": 1, "order": 1},
                    {"id": "item-3", "title": "Chapter 3", "level": 1, "order": 2},
                ],
                "resources": [],
                "style_config": {"version": 1, "preset_id": "test", "style": {}},
            },
        )

        data = response.json()
        assert data["error"] is None
        assert data["data"] is not None

    @pytest.mark.asyncio
    async def test_error_has_null_data(
        self, client: AsyncClient, reset_job_store
    ):
        """Error responses should have data=null."""
        # Invalid request
        response = await client.post(
            "/api/ai/draft/generate",
            json={
                "transcript": "short",  # Invalid
                "outline": [],  # Invalid
                "resources": [],
                "style_config": {},
            },
        )

        data = response.json()
        assert data["data"] is None
        assert data["error"] is not None

    @pytest.mark.asyncio
    async def test_error_has_code_and_message(
        self, client: AsyncClient, reset_job_store
    ):
        """Error responses should have both code and message."""
        response = await client.get("/api/ai/draft/status/nonexistent")

        data = response.json()
        assert "code" in data["error"]
        assert "message" in data["error"]
        assert isinstance(data["error"]["code"], str)
        assert isinstance(data["error"]["message"], str)


class TestErrorHandling:
    """Tests for error handling in draft generation."""

    @pytest.mark.asyncio
    async def test_failed_job_returns_error_details(
        self, client: AsyncClient, reset_job_store
    ):
        """Failed job status should include error_code and error_message."""
        store = get_job_store()

        # Manually create a failed job with error details
        job_id = await store.create_job()
        await store.update_job(
            job_id,
            status=JobStatus.failed,
            total_chapters=5,
            current_chapter=3,
            error="LLM API rate limit exceeded",
            error_code="GENERATION_ERROR",
        )

        # Get status
        response = await client.get(f"/api/ai/draft/status/{job_id}")

        assert response.status_code == 200
        data = response.json()["data"]

        assert data["status"] == "failed"
        assert data["error_code"] == "GENERATION_ERROR"
        assert data["error_message"] == "LLM API rate limit exceeded"

    @pytest.mark.asyncio
    async def test_failed_job_returns_progress(
        self, client: AsyncClient, reset_job_store
    ):
        """Failed job status should include progress to show where it stopped."""
        store = get_job_store()

        # Manually create a failed job with progress
        job_id = await store.create_job()
        await store.update_job(
            job_id,
            status=JobStatus.failed,
            total_chapters=5,
            current_chapter=3,
            chapters_completed=["# Chapter 1\n\nContent 1", "# Chapter 2\n\nContent 2"],
            error="Connection timeout",
            error_code="GENERATION_ERROR",
        )

        # Get status
        response = await client.get(f"/api/ai/draft/status/{job_id}")

        assert response.status_code == 200
        data = response.json()["data"]

        assert data["status"] == "failed"
        assert data["progress"] is not None
        assert data["progress"]["total_chapters"] == 5
        assert data["progress"]["current_chapter"] == 3
        assert data["progress"]["chapters_completed"] == 2
        assert data["chapters_available"] == 2
        assert data["partial_draft_markdown"] is not None

    @pytest.mark.asyncio
    async def test_completed_job_returns_finalized_progress(
        self, client: AsyncClient, reset_job_store
    ):
        """Completed job should return 100% finalized progress."""
        store = get_job_store()

        # Manually create a completed job
        job_id = await store.create_job()
        await store.update_job(
            job_id,
            status=JobStatus.completed,
            total_chapters=8,
            chapters_completed=[f"# Chapter {i}\n\nContent {i}" for i in range(1, 9)],
            draft_markdown="# Book\n\n" + "\n\n".join([f"# Chapter {i}\n\nContent {i}" for i in range(1, 9)]),
        )

        # Get status
        response = await client.get(f"/api/ai/draft/status/{job_id}")

        assert response.status_code == 200
        data = response.json()["data"]

        assert data["status"] == "completed"
        # Progress should be finalized to 100%
        assert data["progress"] is not None
        assert data["progress"]["total_chapters"] == 8
        assert data["progress"]["current_chapter"] == 8  # Finalized to total
        assert data["progress"]["chapters_completed"] == 8  # All chapters
        assert data["progress"]["current_chapter_title"] is None  # No active chapter
        assert data["progress"]["estimated_remaining_seconds"] == 0  # No time remaining

    @pytest.mark.asyncio
    async def test_completed_job_has_no_error_fields(
        self, client: AsyncClient, reset_job_store
    ):
        """Completed job status should not include error fields."""
        store = get_job_store()

        # Manually create a completed job
        job_id = await store.create_job()
        await store.update_job(
            job_id,
            status=JobStatus.completed,
            total_chapters=2,
            chapters_completed=["# Chapter 1\n\nContent 1", "# Chapter 2\n\nContent 2"],
            draft_markdown="# Book\n\n# Chapter 1\n\nContent 1\n\n# Chapter 2\n\nContent 2",
        )

        # Get status
        response = await client.get(f"/api/ai/draft/status/{job_id}")

        assert response.status_code == 200
        data = response.json()["data"]

        assert data["status"] == "completed"
        assert data.get("error_code") is None
        assert data.get("error_message") is None


class TestProgressAndPartialResults:
    """Tests for progress tracking and partial results."""

    @pytest.mark.asyncio
    async def test_status_returns_partial_draft_during_generation(
        self, client: AsyncClient, reset_job_store
    ):
        """Status should include partial_draft_markdown when chapters are completed."""
        store = get_job_store()

        # Manually create a job with partial results
        job_id = await store.create_job()
        await store.update_job(
            job_id,
            status=JobStatus.generating,
            total_chapters=3,
            current_chapter=2,
            chapters_completed=["# Chapter 1\n\nContent 1"],
        )

        # Get status
        status = await get_job_status(job_id)

        assert status is not None
        assert status.status == JobStatus.generating
        assert status.partial_draft_markdown is not None
        assert "Chapter 1" in status.partial_draft_markdown
        assert status.chapters_available == 1

    @pytest.mark.asyncio
    async def test_cancelled_job_preserves_partial_results(
        self, client: AsyncClient, reset_job_store
    ):
        """Cancelled jobs should preserve completed chapters."""
        store = get_job_store()

        # Manually create a cancelled job with partial results
        job_id = await store.create_job()
        await store.update_job(
            job_id,
            status=JobStatus.cancelled,
            total_chapters=5,
            chapters_completed=[
                "# Chapter 1\n\nContent 1",
                "# Chapter 2\n\nContent 2",
            ],
        )

        # Get status
        response = await client.get(f"/api/ai/draft/status/{job_id}")

        assert response.status_code == 200
        data = response.json()["data"]

        assert data["status"] == "cancelled"
        assert data["partial_draft_markdown"] is not None
        assert "Chapter 1" in data["partial_draft_markdown"]
        assert "Chapter 2" in data["partial_draft_markdown"]
        assert data["chapters_available"] == 2
