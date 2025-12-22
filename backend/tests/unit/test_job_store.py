"""Unit tests for job store implementations.

Tests cover:
- InMemoryJobStore operations
- MongoJobStore operations
- Job lifecycle (create, update, delete)
- TTL cleanup
- Persistence across operations
"""

import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import patch, MagicMock

import pytest
import pytest_asyncio
from mongomock_motor import AsyncMongoMockClient

from src.models import JobStatus, GenerationJob, DraftPlan, ChapterPlan, VisualPlan, GenerationMetadata
from src.services.job_store import (
    InMemoryJobStore,
    MongoJobStore,
    set_job_store,
    get_job_store,
)
from src.db import mongo


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def in_memory_store():
    """Fresh in-memory job store for testing."""
    return InMemoryJobStore()


@pytest_asyncio.fixture
async def mongo_store():
    """MongoDB job store with mock backend."""
    # Create mock client
    mock_client = AsyncMongoMockClient()
    mock_database = mock_client["test_jobs"]

    # Replace the real client with mock
    mongo.set_client(mock_client)

    store = MongoJobStore()

    yield store

    # Cleanup
    mongo.set_client(None)


@pytest.fixture
def sample_draft_plan():
    """Sample DraftPlan for testing."""
    return DraftPlan(
        version=1,
        book_title="Test Book",
        chapters=[
            ChapterPlan(
                chapter_number=1,
                title="Chapter 1",
                outline_item_id="ch1",
                goals=["Goal 1"],
                key_points=["Point 1"],
                transcript_segments=[],
                estimated_words=500,
            ),
        ],
        visual_plan=VisualPlan(opportunities=[], assets=[]),
        generation_metadata=GenerationMetadata(
            estimated_total_words=500,
            estimated_generation_time_seconds=30,
            transcript_utilization=0.8,
        ),
    )


# =============================================================================
# InMemoryJobStore Tests
# =============================================================================

class TestInMemoryJobStore:
    """Tests for InMemoryJobStore."""

    @pytest.mark.asyncio
    async def test_create_job_returns_id(self, in_memory_store):
        """Test that create_job returns a unique job ID."""
        job_id = await in_memory_store.create_job()

        assert job_id is not None
        assert len(job_id) > 0

    @pytest.mark.asyncio
    async def test_create_job_with_project_id(self, in_memory_store):
        """Test that create_job stores project_id."""
        job_id = await in_memory_store.create_job(project_id="proj-123")
        job = await in_memory_store.get_job(job_id)

        assert job.project_id == "proj-123"

    @pytest.mark.asyncio
    async def test_get_job_returns_job(self, in_memory_store):
        """Test that get_job returns the correct job."""
        job_id = await in_memory_store.create_job()
        job = await in_memory_store.get_job(job_id)

        assert job is not None
        assert job.job_id == job_id
        assert job.status == JobStatus.queued

    @pytest.mark.asyncio
    async def test_get_job_not_found(self, in_memory_store):
        """Test that get_job returns None for unknown ID."""
        job = await in_memory_store.get_job("nonexistent")
        assert job is None

    @pytest.mark.asyncio
    async def test_update_job_updates_fields(self, in_memory_store):
        """Test that update_job updates job fields."""
        job_id = await in_memory_store.create_job()

        await in_memory_store.update_job(
            job_id,
            status=JobStatus.generating,
            current_chapter=2,
            total_chapters=5,
        )

        job = await in_memory_store.get_job(job_id)
        assert job.status == JobStatus.generating
        assert job.current_chapter == 2
        assert job.total_chapters == 5

    @pytest.mark.asyncio
    async def test_update_job_auto_sets_started_at(self, in_memory_store):
        """Test that update to planning sets started_at."""
        job_id = await in_memory_store.create_job()

        await in_memory_store.update_job(job_id, status=JobStatus.planning)

        job = await in_memory_store.get_job(job_id)
        assert job.started_at is not None

    @pytest.mark.asyncio
    async def test_update_job_auto_sets_completed_at(self, in_memory_store):
        """Test that terminal status sets completed_at."""
        job_id = await in_memory_store.create_job()

        await in_memory_store.update_job(job_id, status=JobStatus.completed)

        job = await in_memory_store.get_job(job_id)
        assert job.completed_at is not None

    @pytest.mark.asyncio
    async def test_delete_job(self, in_memory_store):
        """Test that delete_job removes the job."""
        job_id = await in_memory_store.create_job()
        deleted = await in_memory_store.delete_job(job_id)

        assert deleted is True
        assert await in_memory_store.get_job(job_id) is None

    @pytest.mark.asyncio
    async def test_delete_job_not_found(self, in_memory_store):
        """Test that delete_job returns False for unknown ID."""
        deleted = await in_memory_store.delete_job("nonexistent")
        assert deleted is False

    @pytest.mark.asyncio
    async def test_list_jobs(self, in_memory_store):
        """Test that list_jobs returns all jobs."""
        await in_memory_store.create_job()
        await in_memory_store.create_job()
        await in_memory_store.create_job()

        jobs = await in_memory_store.list_jobs()
        assert len(jobs) == 3

    @pytest.mark.asyncio
    async def test_list_jobs_with_status_filter(self, in_memory_store):
        """Test that list_jobs can filter by status."""
        job_id1 = await in_memory_store.create_job()
        job_id2 = await in_memory_store.create_job()
        await in_memory_store.update_job(job_id1, status=JobStatus.completed)

        jobs = await in_memory_store.list_jobs(status=JobStatus.queued)
        assert len(jobs) == 1
        assert jobs[0].job_id == job_id2


# =============================================================================
# MongoJobStore Tests
# =============================================================================

class TestMongoJobStore:
    """Tests for MongoJobStore."""

    @pytest.mark.asyncio
    async def test_create_job_returns_id(self, mongo_store):
        """Test that create_job returns a unique job ID."""
        job_id = await mongo_store.create_job()

        assert job_id is not None
        assert len(job_id) > 0

    @pytest.mark.asyncio
    async def test_create_job_with_project_id(self, mongo_store):
        """Test that create_job stores project_id."""
        job_id = await mongo_store.create_job(project_id="proj-123")
        job = await mongo_store.get_job(job_id)

        assert job.project_id == "proj-123"

    @pytest.mark.asyncio
    async def test_get_job_returns_job(self, mongo_store):
        """Test that get_job returns the correct job."""
        job_id = await mongo_store.create_job()
        job = await mongo_store.get_job(job_id)

        assert job is not None
        assert job.job_id == job_id
        assert job.status == JobStatus.queued

    @pytest.mark.asyncio
    async def test_get_job_not_found(self, mongo_store):
        """Test that get_job returns None for unknown ID."""
        job = await mongo_store.get_job("nonexistent")
        assert job is None

    @pytest.mark.asyncio
    async def test_update_job_updates_fields(self, mongo_store):
        """Test that update_job updates job fields."""
        job_id = await mongo_store.create_job()

        await mongo_store.update_job(
            job_id,
            status=JobStatus.generating,
            current_chapter=2,
            total_chapters=5,
        )

        job = await mongo_store.get_job(job_id)
        assert job.status == JobStatus.generating
        assert job.current_chapter == 2
        assert job.total_chapters == 5

    @pytest.mark.asyncio
    async def test_update_job_persists_chapters_completed(self, mongo_store):
        """Test that chapters_completed list is persisted."""
        job_id = await mongo_store.create_job()
        chapters = ["## Chapter 1\n\nContent 1", "## Chapter 2\n\nContent 2"]

        await mongo_store.update_job(job_id, chapters_completed=chapters)

        job = await mongo_store.get_job(job_id)
        assert len(job.chapters_completed) == 2
        assert "Chapter 1" in job.chapters_completed[0]

    @pytest.mark.asyncio
    async def test_update_job_persists_draft_plan(self, mongo_store, sample_draft_plan):
        """Test that DraftPlan is persisted correctly."""
        job_id = await mongo_store.create_job()

        await mongo_store.update_job(job_id, draft_plan=sample_draft_plan)

        # Reload job from database
        job = await mongo_store.get_job(job_id)
        assert job.draft_plan is not None
        assert job.draft_plan.book_title == "Test Book"
        assert len(job.draft_plan.chapters) == 1

    @pytest.mark.asyncio
    async def test_job_survives_reload(self, mongo_store):
        """Test that job state persists across get operations."""
        # Create and update job
        job_id = await mongo_store.create_job(project_id="proj-456")
        await mongo_store.update_job(
            job_id,
            status=JobStatus.generating,
            current_chapter=3,
            total_chapters=10,
            chapters_completed=["Chapter 1", "Chapter 2"],
        )

        # Reload job
        job = await mongo_store.get_job(job_id)

        # Verify all fields persisted
        assert job.job_id == job_id
        assert job.project_id == "proj-456"
        assert job.status == JobStatus.generating
        assert job.current_chapter == 3
        assert job.total_chapters == 10
        assert len(job.chapters_completed) == 2

    @pytest.mark.asyncio
    async def test_delete_job(self, mongo_store):
        """Test that delete_job removes the job."""
        job_id = await mongo_store.create_job()
        deleted = await mongo_store.delete_job(job_id)

        assert deleted is True
        assert await mongo_store.get_job(job_id) is None

    @pytest.mark.asyncio
    async def test_list_jobs(self, mongo_store):
        """Test that list_jobs returns all jobs."""
        await mongo_store.create_job()
        await mongo_store.create_job()
        await mongo_store.create_job()

        jobs = await mongo_store.list_jobs()
        assert len(jobs) == 3

    @pytest.mark.asyncio
    async def test_list_jobs_with_status_filter(self, mongo_store):
        """Test that list_jobs can filter by status."""
        job_id1 = await mongo_store.create_job()
        job_id2 = await mongo_store.create_job()
        await mongo_store.update_job(job_id1, status=JobStatus.completed)

        jobs = await mongo_store.list_jobs(status=JobStatus.queued)
        assert len(jobs) == 1
        assert jobs[0].job_id == job_id2

    @pytest.mark.asyncio
    async def test_error_fields_persisted(self, mongo_store):
        """Test that error and error_code are persisted."""
        job_id = await mongo_store.create_job()

        await mongo_store.update_job(
            job_id,
            status=JobStatus.failed,
            error="LLM API timeout",
            error_code="GENERATION_ERROR",
        )

        job = await mongo_store.get_job(job_id)
        assert job.status == JobStatus.failed
        assert job.error == "LLM API timeout"
        assert job.error_code == "GENERATION_ERROR"


# =============================================================================
# TTL and Cleanup Tests
# =============================================================================

class TestTTLCleanup:
    """Tests for TTL cleanup behavior."""

    @pytest.mark.asyncio
    async def test_in_memory_cleanup_removes_expired_jobs(self):
        """Test that cleanup removes expired jobs."""
        # Create store with very short TTL
        store = InMemoryJobStore(ttl_seconds=0)

        job_id = await store.create_job()
        await store.update_job(job_id, status=JobStatus.completed)

        # Wait a moment for completion timestamp
        await asyncio.sleep(0.01)

        # Cleanup should remove the job
        removed = await store.cleanup_expired_jobs()
        assert removed == 1
        assert await store.get_job(job_id) is None

    @pytest.mark.asyncio
    async def test_in_memory_cleanup_keeps_active_jobs(self):
        """Test that cleanup does not remove active jobs."""
        store = InMemoryJobStore(ttl_seconds=0)

        # Create an active job
        job_id = await store.create_job()
        await store.update_job(job_id, status=JobStatus.generating)

        # Cleanup should not remove it
        removed = await store.cleanup_expired_jobs()
        assert removed == 0
        assert await store.get_job(job_id) is not None


# =============================================================================
# Store Selection Tests
# =============================================================================

class TestStoreSelection:
    """Tests for job store backend selection."""

    def test_default_store_is_mongo(self):
        """Test that default store is MongoDB when env not set."""
        set_job_store(None)

        with patch.dict("os.environ", {"JOB_STORE_BACKEND": "mongo"}):
            # Reset singleton
            import src.services.job_store as js
            js._default_store = None

            store = get_job_store()
            assert isinstance(store, MongoJobStore)

    def test_in_memory_store_when_configured(self):
        """Test that in-memory store is used when configured."""
        with patch.dict("os.environ", {"JOB_STORE_BACKEND": "memory"}):
            # Reset singleton
            import src.services.job_store as js
            js._default_store = None

            store = get_job_store()
            assert isinstance(store, InMemoryJobStore)
