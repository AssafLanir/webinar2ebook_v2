"""In-memory job store for draft generation jobs.

MVP storage: jobs are lost on server restart.
Future: Add MongoDB persistence when multi-user support needed.

Features:
- TTL cleanup (1-hour default) via periodic task
- Thread-safe operations via asyncio locks
- Simple CRUD operations
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import uuid4

from src.models import GenerationJob, JobStatus

logger = logging.getLogger(__name__)

# Default TTL for completed/failed jobs (1 hour)
DEFAULT_JOB_TTL_SECONDS = 3600

# How often to run cleanup (5 minutes)
CLEANUP_INTERVAL_SECONDS = 300


class JobStore:
    """In-memory job store with TTL cleanup.

    Thread-safe via asyncio locks for concurrent access.

    Usage:
        store = JobStore()
        job_id = await store.create_job()
        job = await store.get_job(job_id)
        await store.update_job(job_id, status=JobStatus.completed)
    """

    def __init__(self, ttl_seconds: int = DEFAULT_JOB_TTL_SECONDS):
        """Initialize job store.

        Args:
            ttl_seconds: Time-to-live for completed jobs before cleanup.
        """
        self._jobs: dict[str, GenerationJob] = {}
        self._lock = asyncio.Lock()
        self._ttl_seconds = ttl_seconds
        self._cleanup_task: Optional[asyncio.Task] = None

    async def start_cleanup_task(self) -> None:
        """Start the background cleanup task."""
        if self._cleanup_task is None or self._cleanup_task.done():
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())
            logger.info("Job store cleanup task started")

    async def stop_cleanup_task(self) -> None:
        """Stop the background cleanup task."""
        if self._cleanup_task and not self._cleanup_task.done():
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            logger.info("Job store cleanup task stopped")

    async def _cleanup_loop(self) -> None:
        """Periodically clean up expired jobs."""
        while True:
            try:
                await asyncio.sleep(CLEANUP_INTERVAL_SECONDS)
                await self.cleanup_expired_jobs()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in cleanup loop: {e}")

    async def cleanup_expired_jobs(self) -> int:
        """Remove jobs that have been completed for longer than TTL.

        Returns:
            Number of jobs removed.
        """
        async with self._lock:
            now = datetime.now(timezone.utc)
            expired_ids = []

            for job_id, job in self._jobs.items():
                # Only clean up terminal jobs
                if not job.is_terminal():
                    continue

                # Check if past TTL
                if job.completed_at:
                    age = (now - job.completed_at).total_seconds()
                    if age > self._ttl_seconds:
                        expired_ids.append(job_id)

            for job_id in expired_ids:
                del self._jobs[job_id]

            if expired_ids:
                logger.info(f"Cleaned up {len(expired_ids)} expired jobs")

            return len(expired_ids)

    async def create_job(
        self,
        project_id: Optional[str] = None,
    ) -> str:
        """Create a new generation job.

        Args:
            project_id: Optional associated project ID.

        Returns:
            The new job's ID.
        """
        job_id = str(uuid4())
        job = GenerationJob(
            job_id=job_id,
            project_id=project_id,
            status=JobStatus.queued,
            created_at=datetime.now(timezone.utc),
        )

        async with self._lock:
            self._jobs[job_id] = job

        logger.debug(f"Created job {job_id}")
        return job_id

    async def get_job(self, job_id: str) -> Optional[GenerationJob]:
        """Get a job by ID.

        Args:
            job_id: The job identifier.

        Returns:
            The job if found, None otherwise.
        """
        async with self._lock:
            return self._jobs.get(job_id)

    async def update_job(
        self,
        job_id: str,
        **updates,
    ) -> Optional[GenerationJob]:
        """Update a job's fields.

        Args:
            job_id: The job identifier.
            **updates: Field updates to apply.

        Returns:
            The updated job if found, None otherwise.
        """
        async with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return None

            # Apply updates
            for key, value in updates.items():
                if hasattr(job, key):
                    setattr(job, key, value)
                else:
                    logger.warning(f"Unknown field {key} for job update")

            # Auto-set timestamps
            if updates.get("status") == JobStatus.planning and not job.started_at:
                job.started_at = datetime.now(timezone.utc)
            if updates.get("status") in (
                JobStatus.completed,
                JobStatus.cancelled,
                JobStatus.failed,
            ):
                job.completed_at = datetime.now(timezone.utc)

            return job

    async def delete_job(self, job_id: str) -> bool:
        """Delete a job.

        Args:
            job_id: The job identifier.

        Returns:
            True if deleted, False if not found.
        """
        async with self._lock:
            if job_id in self._jobs:
                del self._jobs[job_id]
                logger.debug(f"Deleted job {job_id}")
                return True
            return False

    async def list_jobs(
        self,
        status: Optional[JobStatus] = None,
        limit: int = 100,
    ) -> list[GenerationJob]:
        """List jobs with optional filtering.

        Args:
            status: Filter by status (optional).
            limit: Maximum number of jobs to return.

        Returns:
            List of jobs matching criteria.
        """
        async with self._lock:
            jobs = list(self._jobs.values())

            if status:
                jobs = [j for j in jobs if j.status == status]

            # Sort by created_at descending
            jobs.sort(key=lambda j: j.created_at, reverse=True)

            return jobs[:limit]

    async def count_active_jobs(self) -> int:
        """Count jobs that are currently running.

        Returns:
            Number of active (non-terminal) jobs.
        """
        async with self._lock:
            return sum(
                1 for job in self._jobs.values()
                if not job.is_terminal()
            )

    def __len__(self) -> int:
        """Return total number of jobs in store."""
        return len(self._jobs)


# Module-level singleton instance
_default_store: Optional[JobStore] = None


def get_job_store() -> JobStore:
    """Get the default job store singleton.

    Creates the store on first access.
    """
    global _default_store
    if _default_store is None:
        _default_store = JobStore()
    return _default_store


async def create_job(project_id: Optional[str] = None) -> str:
    """Create a new job using the default store."""
    return await get_job_store().create_job(project_id=project_id)


async def get_job(job_id: str) -> Optional[GenerationJob]:
    """Get a job by ID using the default store."""
    return await get_job_store().get_job(job_id)


async def update_job(job_id: str, **updates) -> Optional[GenerationJob]:
    """Update a job using the default store."""
    return await get_job_store().update_job(job_id, **updates)


async def delete_job(job_id: str) -> bool:
    """Delete a job using the default store."""
    return await get_job_store().delete_job(job_id)
