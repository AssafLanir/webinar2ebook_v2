"""Tests for theme job store."""

import pytest
from src.models.theme_job import ThemeJob, ThemeJobStatus
from src.services.theme_job_store import InMemoryThemeJobStore


@pytest.fixture
def store():
    return InMemoryThemeJobStore()


class TestThemeJobStore:
    @pytest.mark.asyncio
    async def test_create_job(self, store):
        job_id = await store.create_job(project_id="proj-1")
        assert job_id is not None

    @pytest.mark.asyncio
    async def test_get_job(self, store):
        job_id = await store.create_job(project_id="proj-1")
        job = await store.get_job(job_id)
        assert job is not None
        assert job.job_id == job_id
        assert job.status == ThemeJobStatus.QUEUED

    @pytest.mark.asyncio
    async def test_update_job(self, store):
        job_id = await store.create_job(project_id="proj-1")
        updated = await store.update_job(job_id, status=ThemeJobStatus.COMPLETED)
        assert updated.status == ThemeJobStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_get_nonexistent_job(self, store):
        job = await store.get_job("nonexistent")
        assert job is None

    @pytest.mark.asyncio
    async def test_update_to_processing_sets_started_at(self, store):
        job_id = await store.create_job(project_id="proj-1")
        job = await store.get_job(job_id)
        assert job.started_at is None

        updated = await store.update_job(job_id, status=ThemeJobStatus.PROCESSING)
        assert updated.started_at is not None

    @pytest.mark.asyncio
    async def test_update_to_terminal_sets_completed_at(self, store):
        job_id = await store.create_job(project_id="proj-1")
        await store.update_job(job_id, status=ThemeJobStatus.PROCESSING)

        for status in [ThemeJobStatus.COMPLETED, ThemeJobStatus.FAILED, ThemeJobStatus.CANCELLED]:
            job_id = await store.create_job(project_id="proj-1")
            updated = await store.update_job(job_id, status=status)
            assert updated.completed_at is not None

    @pytest.mark.asyncio
    async def test_delete_job(self, store):
        job_id = await store.create_job(project_id="proj-1")
        assert await store.get_job(job_id) is not None

        deleted = await store.delete_job(job_id)
        assert deleted is True
        assert await store.get_job(job_id) is None

    @pytest.mark.asyncio
    async def test_delete_nonexistent_job(self, store):
        deleted = await store.delete_job("nonexistent")
        assert deleted is False


class TestThemeJob:
    def test_is_terminal_completed(self):
        job = ThemeJob(
            job_id="test",
            project_id="proj-1",
            status=ThemeJobStatus.COMPLETED,
            created_at="2024-01-01T00:00:00Z",
        )
        assert job.is_terminal() is True

    def test_is_terminal_failed(self):
        job = ThemeJob(
            job_id="test",
            project_id="proj-1",
            status=ThemeJobStatus.FAILED,
            created_at="2024-01-01T00:00:00Z",
        )
        assert job.is_terminal() is True

    def test_is_terminal_cancelled(self):
        job = ThemeJob(
            job_id="test",
            project_id="proj-1",
            status=ThemeJobStatus.CANCELLED,
            created_at="2024-01-01T00:00:00Z",
        )
        assert job.is_terminal() is True

    def test_is_not_terminal_queued(self):
        job = ThemeJob(
            job_id="test",
            project_id="proj-1",
            status=ThemeJobStatus.QUEUED,
            created_at="2024-01-01T00:00:00Z",
        )
        assert job.is_terminal() is False

    def test_is_not_terminal_processing(self):
        job = ThemeJob(
            job_id="test",
            project_id="proj-1",
            status=ThemeJobStatus.PROCESSING,
            created_at="2024-01-01T00:00:00Z",
        )
        assert job.is_terminal() is False
