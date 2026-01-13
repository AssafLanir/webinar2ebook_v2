"""Theme job store for proposal jobs.

In-memory store for tracking theme proposal job status.
"""

import asyncio
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from src.models.theme_job import ThemeJob, ThemeJobStatus


class InMemoryThemeJobStore:
    """In-memory store for theme proposal jobs."""

    def __init__(self):
        self._jobs: dict[str, ThemeJob] = {}
        self._lock = asyncio.Lock()

    async def create_job(self, project_id: str) -> str:
        """Create a new theme proposal job.

        Args:
            project_id: ID of the project for this job

        Returns:
            The new job ID
        """
        job_id = str(uuid4())
        job = ThemeJob(
            job_id=job_id,
            project_id=project_id,
            status=ThemeJobStatus.QUEUED,
            created_at=datetime.now(timezone.utc),
        )
        async with self._lock:
            self._jobs[job_id] = job
        return job_id

    async def get_job(self, job_id: str) -> Optional[ThemeJob]:
        """Get a job by ID.

        Args:
            job_id: The job ID to look up

        Returns:
            The job if found, None otherwise
        """
        async with self._lock:
            return self._jobs.get(job_id)

    async def update_job(self, job_id: str, **updates) -> Optional[ThemeJob]:
        """Update a job with the given fields.

        Automatically sets started_at when transitioning to PROCESSING,
        and completed_at when transitioning to terminal states.

        Args:
            job_id: The job ID to update
            **updates: Fields to update

        Returns:
            The updated job if found, None otherwise
        """
        async with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return None

            for key, value in updates.items():
                if hasattr(job, key):
                    setattr(job, key, value)

            # Auto-set timestamps based on status transitions
            if updates.get("status") == ThemeJobStatus.PROCESSING:
                job.started_at = datetime.now(timezone.utc)
            if updates.get("status") in (
                ThemeJobStatus.COMPLETED,
                ThemeJobStatus.FAILED,
                ThemeJobStatus.CANCELLED,
            ):
                job.completed_at = datetime.now(timezone.utc)

            return job

    async def delete_job(self, job_id: str) -> bool:
        """Delete a job by ID.

        Args:
            job_id: The job ID to delete

        Returns:
            True if deleted, False if not found
        """
        async with self._lock:
            if job_id in self._jobs:
                del self._jobs[job_id]
                return True
            return False


# Singleton instance
_store: Optional[InMemoryThemeJobStore] = None


def get_theme_job_store() -> InMemoryThemeJobStore:
    """Get the singleton theme job store instance."""
    global _store
    if _store is None:
        _store = InMemoryThemeJobStore()
    return _store
