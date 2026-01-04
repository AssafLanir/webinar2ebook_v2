"""Job store for draft generation jobs.

Supports two backends:
1. MongoDB (durable) - jobs survive server restart
2. In-memory (fallback) - for testing or when MongoDB unavailable

Features:
- TTL cleanup (1-hour default) via MongoDB TTL index or periodic task
- Thread-safe operations via asyncio locks
- Simple CRUD operations
"""

from __future__ import annotations

import asyncio
import logging
import os
from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import uuid4

from src.models import GenerationJob, JobStatus, DraftPlan, VisualPlan
from src.models.style_config import ContentMode

logger = logging.getLogger(__name__)

# Default TTL for completed/failed jobs (1 hour)
DEFAULT_JOB_TTL_SECONDS = 3600

# How often to run cleanup (5 minutes)
CLEANUP_INTERVAL_SECONDS = 300

# Collection name for MongoDB storage
JOBS_COLLECTION = "generation_jobs"


class BaseJobStore(ABC):
    """Abstract base class for job stores.

    Implementations must provide CRUD operations and lifecycle hooks.
    Lifecycle hooks (start/stop_cleanup_task) are called by FastAPI lifespan
    and may be no-ops if cleanup is handled externally (e.g., MongoDB TTL).
    """

    async def start_cleanup_task(self) -> None:
        """Called on application startup. Override for cleanup initialization."""
        pass

    async def stop_cleanup_task(self) -> None:
        """Called on application shutdown. Override to cancel background tasks."""
        pass

    @abstractmethod
    async def create_job(self, project_id: Optional[str] = None) -> str:
        """Create a new generation job."""
        pass

    @abstractmethod
    async def get_job(self, job_id: str) -> Optional[GenerationJob]:
        """Get a job by ID."""
        pass

    @abstractmethod
    async def update_job(self, job_id: str, **updates) -> Optional[GenerationJob]:
        """Update a job's fields."""
        pass

    @abstractmethod
    async def delete_job(self, job_id: str) -> bool:
        """Delete a job."""
        pass

    @abstractmethod
    async def list_jobs(
        self,
        status: Optional[JobStatus] = None,
        limit: int = 100,
    ) -> list[GenerationJob]:
        """List jobs with optional filtering."""
        pass


class InMemoryJobStore(BaseJobStore):
    """In-memory job store with TTL cleanup.

    Thread-safe via asyncio locks for concurrent access.
    Jobs are lost on server restart.
    """

    def __init__(self, ttl_seconds: int = DEFAULT_JOB_TTL_SECONDS):
        """Initialize job store."""
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
        """Remove jobs that have been completed for longer than TTL."""
        async with self._lock:
            now = datetime.now(timezone.utc)
            expired_ids = []

            for job_id, job in self._jobs.items():
                if not job.is_terminal():
                    continue
                if job.completed_at:
                    age = (now - job.completed_at).total_seconds()
                    if age > self._ttl_seconds:
                        expired_ids.append(job_id)

            for job_id in expired_ids:
                del self._jobs[job_id]

            if expired_ids:
                logger.info(f"Cleaned up {len(expired_ids)} expired jobs")

            return len(expired_ids)

    async def create_job(self, project_id: Optional[str] = None) -> str:
        """Create a new generation job."""
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
        """Get a job by ID."""
        async with self._lock:
            return self._jobs.get(job_id)

    async def update_job(self, job_id: str, **updates) -> Optional[GenerationJob]:
        """Update a job's fields."""
        async with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return None

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
        """Delete a job."""
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
        """List jobs with optional filtering."""
        async with self._lock:
            jobs = list(self._jobs.values())
            if status:
                jobs = [j for j in jobs if j.status == status]
            jobs.sort(key=lambda j: j.created_at, reverse=True)
            return jobs[:limit]

    async def count_active_jobs(self) -> int:
        """Count jobs that are currently running."""
        async with self._lock:
            return sum(1 for job in self._jobs.values() if not job.is_terminal())

    def __len__(self) -> int:
        """Return total number of jobs in store."""
        return len(self._jobs)


class MongoJobStore(BaseJobStore):
    """MongoDB-backed job store with TTL index.

    Jobs persist across server restarts.
    Uses MongoDB TTL index for automatic cleanup (no background task needed).
    """

    def __init__(self, ttl_seconds: int = DEFAULT_JOB_TTL_SECONDS):
        """Initialize MongoDB job store."""
        self._ttl_seconds = ttl_seconds
        self._index_created = False

    async def start_cleanup_task(self) -> None:
        """No-op: MongoDB TTL index handles cleanup automatically."""
        await self.ensure_indexes()

    async def stop_cleanup_task(self) -> None:
        """No-op: MongoDB TTL index handles cleanup automatically."""
        pass

    async def _get_collection(self):
        """Get the MongoDB collection."""
        from src.db.mongo import get_database
        db = await get_database()
        return db[JOBS_COLLECTION]

    async def ensure_indexes(self) -> None:
        """Create TTL index on expires_at field if not exists."""
        if self._index_created:
            return

        try:
            collection = await self._get_collection()
            # Create TTL index - MongoDB automatically deletes expired documents
            await collection.create_index(
                "expires_at",
                expireAfterSeconds=0,
                background=True,
            )
            # Create index on job_id for fast lookups
            await collection.create_index("job_id", unique=True)
            # Create index on status for filtering
            await collection.create_index("status")
            self._index_created = True
            logger.info("MongoDB job store indexes created")
        except Exception as e:
            logger.warning(f"Failed to create MongoDB indexes: {e}")

    def _job_to_doc(self, job: GenerationJob) -> dict:
        """Convert GenerationJob to MongoDB document."""
        doc = {
            "job_id": job.job_id,
            "project_id": job.project_id,
            "status": job.status.value,
            "created_at": job.created_at,
            "started_at": job.started_at,
            "completed_at": job.completed_at,
            "current_chapter": job.current_chapter,
            "total_chapters": job.total_chapters,
            "chapters_completed": job.chapters_completed,
            "draft_markdown": job.draft_markdown,
            "cancel_requested": job.cancel_requested,
            "error": job.error,
            "error_code": job.error_code,
            # Evidence Map fields (Spec 009)
            "evidence_map": job.evidence_map,
            "content_mode": job.content_mode.value if job.content_mode else None,
            "constraint_warnings": job.constraint_warnings,
        }

        # Serialize complex objects
        if job.draft_plan:
            doc["draft_plan"] = job.draft_plan.model_dump()
        if job.visual_plan:
            doc["visual_plan"] = job.visual_plan.model_dump()

        # Set expires_at for TTL cleanup
        if job.is_terminal() and job.completed_at:
            doc["expires_at"] = job.completed_at + timedelta(seconds=self._ttl_seconds)
        else:
            doc["expires_at"] = None

        return doc

    def _doc_to_job(self, doc: dict) -> GenerationJob:
        """Convert MongoDB document to GenerationJob."""
        draft_plan = None
        if doc.get("draft_plan"):
            draft_plan = DraftPlan.model_validate(doc["draft_plan"])

        visual_plan = None
        if doc.get("visual_plan"):
            visual_plan = VisualPlan.model_validate(doc["visual_plan"])

        # Deserialize content_mode (Spec 009)
        content_mode = None
        if doc.get("content_mode"):
            content_mode = ContentMode(doc["content_mode"])

        return GenerationJob(
            job_id=doc["job_id"],
            project_id=doc.get("project_id"),
            status=JobStatus(doc["status"]),
            created_at=doc["created_at"],
            started_at=doc.get("started_at"),
            completed_at=doc.get("completed_at"),
            current_chapter=doc.get("current_chapter", 0),
            total_chapters=doc.get("total_chapters", 0),
            chapters_completed=doc.get("chapters_completed", []),
            draft_plan=draft_plan,
            visual_plan=visual_plan,
            draft_markdown=doc.get("draft_markdown"),
            cancel_requested=doc.get("cancel_requested", False),
            error=doc.get("error"),
            error_code=doc.get("error_code"),
            # Evidence Map fields (Spec 009)
            evidence_map=doc.get("evidence_map"),
            content_mode=content_mode,
            constraint_warnings=doc.get("constraint_warnings", []),
        )

    async def create_job(self, project_id: Optional[str] = None) -> str:
        """Create a new generation job in MongoDB."""
        await self.ensure_indexes()

        job_id = str(uuid4())
        job = GenerationJob(
            job_id=job_id,
            project_id=project_id,
            status=JobStatus.queued,
            created_at=datetime.now(timezone.utc),
        )

        collection = await self._get_collection()
        doc = self._job_to_doc(job)
        await collection.insert_one(doc)

        logger.debug(f"Created job {job_id} in MongoDB")
        return job_id

    async def get_job(self, job_id: str) -> Optional[GenerationJob]:
        """Get a job by ID from MongoDB."""
        collection = await self._get_collection()
        doc = await collection.find_one({"job_id": job_id})

        if not doc:
            return None

        return self._doc_to_job(doc)

    async def update_job(self, job_id: str, **updates) -> Optional[GenerationJob]:
        """Update a job's fields in MongoDB."""
        collection = await self._get_collection()

        # Fetch current job
        doc = await collection.find_one({"job_id": job_id})
        if not doc:
            return None

        job = self._doc_to_job(doc)

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

        # Save back to MongoDB
        new_doc = self._job_to_doc(job)
        await collection.replace_one({"job_id": job_id}, new_doc)

        return job

    async def delete_job(self, job_id: str) -> bool:
        """Delete a job from MongoDB."""
        collection = await self._get_collection()
        result = await collection.delete_one({"job_id": job_id})
        deleted = result.deleted_count > 0

        if deleted:
            logger.debug(f"Deleted job {job_id} from MongoDB")

        return deleted

    async def list_jobs(
        self,
        status: Optional[JobStatus] = None,
        limit: int = 100,
    ) -> list[GenerationJob]:
        """List jobs with optional filtering."""
        collection = await self._get_collection()

        query = {}
        if status:
            query["status"] = status.value

        cursor = collection.find(query).sort("created_at", -1).limit(limit)
        docs = await cursor.to_list(length=limit)

        return [self._doc_to_job(doc) for doc in docs]

    async def count_active_jobs(self) -> int:
        """Count jobs that are currently running."""
        collection = await self._get_collection()
        count = await collection.count_documents({
            "status": {"$in": [
                JobStatus.queued.value,
                JobStatus.planning.value,
                JobStatus.evidence_map.value,
                JobStatus.generating.value,
            ]}
        })
        return count


# Alias for backward compatibility
JobStore = InMemoryJobStore

# Module-level singleton instance
_default_store: Optional[BaseJobStore] = None


def get_job_store() -> BaseJobStore:
    """Get the default job store singleton.

    Uses MongoDB if available, falls back to in-memory.
    """
    global _default_store
    if _default_store is None:
        # Check if MongoDB should be used
        use_mongo = os.getenv("JOB_STORE_BACKEND", "mongo").lower() == "mongo"
        if use_mongo:
            _default_store = MongoJobStore()
            logger.info("Using MongoDB job store")
        else:
            _default_store = InMemoryJobStore()
            logger.info("Using in-memory job store")
    return _default_store


def set_job_store(store: BaseJobStore) -> None:
    """Set the job store instance (for testing)."""
    global _default_store
    _default_store = store


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
