"""Job store for QA analysis jobs.

T016: Reuses pattern from job_store.py but simplified for QA.

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

from src.models.qa_job import QAJob, QAJobStatus
from src.models.qa_report import QAReport

logger = logging.getLogger(__name__)

# Default TTL for completed/failed jobs (1 hour)
DEFAULT_QA_JOB_TTL_SECONDS = 3600

# How often to run cleanup (5 minutes)
CLEANUP_INTERVAL_SECONDS = 300

# Collection name for MongoDB storage
QA_JOBS_COLLECTION = "qa_jobs"


class BaseQAJobStore(ABC):
    """Abstract base class for QA job stores.

    Implementations must provide CRUD operations and lifecycle hooks.
    """

    async def start_cleanup_task(self) -> None:
        """Called on application startup. Override for cleanup initialization."""
        pass

    async def stop_cleanup_task(self) -> None:
        """Called on application shutdown. Override to cancel background tasks."""
        pass

    @abstractmethod
    async def create_job(self, project_id: str) -> str:
        """Create a new QA job."""
        pass

    @abstractmethod
    async def get_job(self, job_id: str) -> Optional[QAJob]:
        """Get a job by ID."""
        pass

    @abstractmethod
    async def update_job(self, job_id: str, **updates) -> Optional[QAJob]:
        """Update a job's fields."""
        pass

    @abstractmethod
    async def delete_job(self, job_id: str) -> bool:
        """Delete a job."""
        pass

    @abstractmethod
    async def get_job_for_project(self, project_id: str) -> Optional[QAJob]:
        """Get the most recent job for a project."""
        pass


class InMemoryQAJobStore(BaseQAJobStore):
    """In-memory QA job store with TTL cleanup.

    Thread-safe via asyncio locks for concurrent access.
    Jobs are lost on server restart.
    """

    def __init__(self, ttl_seconds: int = DEFAULT_QA_JOB_TTL_SECONDS):
        """Initialize job store."""
        self._jobs: dict[str, QAJob] = {}
        self._lock = asyncio.Lock()
        self._ttl_seconds = ttl_seconds
        self._cleanup_task: Optional[asyncio.Task] = None

    async def start_cleanup_task(self) -> None:
        """Start the background cleanup task."""
        if self._cleanup_task is None or self._cleanup_task.done():
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())
            logger.info("QA job store cleanup task started")

    async def stop_cleanup_task(self) -> None:
        """Stop the background cleanup task."""
        if self._cleanup_task and not self._cleanup_task.done():
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            logger.info("QA job store cleanup task stopped")

    async def _cleanup_loop(self) -> None:
        """Periodically clean up expired jobs."""
        while True:
            try:
                await asyncio.sleep(CLEANUP_INTERVAL_SECONDS)
                await self._cleanup_expired_jobs()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in QA cleanup loop: {e}")

    async def _cleanup_expired_jobs(self) -> int:
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
                logger.info(f"Cleaned up {len(expired_ids)} expired QA jobs")

            return len(expired_ids)

    async def create_job(self, project_id: str) -> str:
        """Create a new QA job."""
        job_id = str(uuid4())
        job = QAJob(
            job_id=job_id,
            project_id=project_id,
            status=QAJobStatus.queued,
            created_at=datetime.now(timezone.utc),
        )

        async with self._lock:
            self._jobs[job_id] = job

        logger.debug(f"Created QA job {job_id}")
        return job_id

    async def get_job(self, job_id: str) -> Optional[QAJob]:
        """Get a job by ID."""
        async with self._lock:
            return self._jobs.get(job_id)

    async def update_job(self, job_id: str, **updates) -> Optional[QAJob]:
        """Update a job's fields."""
        async with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return None

            for key, value in updates.items():
                if hasattr(job, key):
                    setattr(job, key, value)
                else:
                    logger.warning(f"Unknown field {key} for QA job update")

            return job

    async def delete_job(self, job_id: str) -> bool:
        """Delete a job."""
        async with self._lock:
            if job_id in self._jobs:
                del self._jobs[job_id]
                logger.debug(f"Deleted QA job {job_id}")
                return True
            return False

    async def get_job_for_project(self, project_id: str) -> Optional[QAJob]:
        """Get the most recent job for a project."""
        async with self._lock:
            matching = [
                job for job in self._jobs.values()
                if job.project_id == project_id
            ]
            if not matching:
                return None
            # Return most recent
            return max(matching, key=lambda j: j.created_at)

    def __len__(self) -> int:
        """Return total number of jobs in store."""
        return len(self._jobs)


class MongoQAJobStore(BaseQAJobStore):
    """MongoDB-backed QA job store with TTL index.

    Jobs persist across server restarts.
    Uses MongoDB TTL index for automatic cleanup.
    """

    def __init__(self, ttl_seconds: int = DEFAULT_QA_JOB_TTL_SECONDS):
        """Initialize MongoDB QA job store."""
        self._ttl_seconds = ttl_seconds
        self._index_created = False

    async def start_cleanup_task(self) -> None:
        """Ensure indexes on startup."""
        await self._ensure_indexes()

    async def _get_collection(self):
        """Get the MongoDB collection."""
        from src.db.mongo import get_database
        db = await get_database()
        return db[QA_JOBS_COLLECTION]

    async def _ensure_indexes(self) -> None:
        """Create TTL index on expires_at field if not exists."""
        if self._index_created:
            return

        try:
            collection = await self._get_collection()
            # Create TTL index
            await collection.create_index(
                "expires_at",
                expireAfterSeconds=0,
                background=True,
            )
            # Create index on job_id for fast lookups
            await collection.create_index("job_id", unique=True)
            # Create index on project_id for filtering
            await collection.create_index("project_id")
            self._index_created = True
            logger.info("MongoDB QA job store indexes created")
        except Exception as e:
            logger.warning(f"Failed to create MongoDB QA indexes: {e}")

    def _job_to_doc(self, job: QAJob) -> dict:
        """Convert QAJob to MongoDB document."""
        doc = {
            "job_id": job.job_id,
            "project_id": job.project_id,
            "status": job.status.value,
            "created_at": job.created_at,
            "started_at": job.started_at,
            "completed_at": job.completed_at,
            "progress_pct": job.progress_pct,
            "current_stage": job.current_stage,
            "cancel_requested": job.cancel_requested,
            "error": job.error,
            "error_code": job.error_code,
        }

        # Serialize report if present
        if job.report:
            doc["report"] = job.report.model_dump(mode="json")

        # Set expires_at for TTL cleanup
        if job.is_terminal() and job.completed_at:
            doc["expires_at"] = job.completed_at + timedelta(seconds=self._ttl_seconds)
        else:
            doc["expires_at"] = None

        return doc

    def _doc_to_job(self, doc: dict) -> QAJob:
        """Convert MongoDB document to QAJob."""
        report = None
        if doc.get("report"):
            report = QAReport.model_validate(doc["report"])

        return QAJob(
            job_id=doc["job_id"],
            project_id=doc["project_id"],
            status=QAJobStatus(doc["status"]),
            created_at=doc["created_at"],
            started_at=doc.get("started_at"),
            completed_at=doc.get("completed_at"),
            progress_pct=doc.get("progress_pct", 0),
            current_stage=doc.get("current_stage"),
            report=report,
            cancel_requested=doc.get("cancel_requested", False),
            error=doc.get("error"),
            error_code=doc.get("error_code"),
        )

    async def create_job(self, project_id: str) -> str:
        """Create a new QA job in MongoDB."""
        await self._ensure_indexes()

        job_id = str(uuid4())
        job = QAJob(
            job_id=job_id,
            project_id=project_id,
            status=QAJobStatus.queued,
            created_at=datetime.now(timezone.utc),
        )

        collection = await self._get_collection()
        doc = self._job_to_doc(job)
        await collection.insert_one(doc)

        logger.debug(f"Created QA job {job_id} in MongoDB")
        return job_id

    async def get_job(self, job_id: str) -> Optional[QAJob]:
        """Get a job by ID from MongoDB."""
        collection = await self._get_collection()
        doc = await collection.find_one({"job_id": job_id})

        if not doc:
            return None

        return self._doc_to_job(doc)

    async def update_job(self, job_id: str, **updates) -> Optional[QAJob]:
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
                logger.warning(f"Unknown field {key} for QA job update")

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
            logger.debug(f"Deleted QA job {job_id} from MongoDB")

        return deleted

    async def get_job_for_project(self, project_id: str) -> Optional[QAJob]:
        """Get the most recent job for a project."""
        collection = await self._get_collection()
        doc = await collection.find_one(
            {"project_id": project_id},
            sort=[("created_at", -1)]
        )

        if not doc:
            return None

        return self._doc_to_job(doc)


# Module-level singleton instance
_qa_job_store: Optional[BaseQAJobStore] = None


def get_qa_job_store() -> BaseQAJobStore:
    """Get the default QA job store singleton.

    Uses MongoDB if available, falls back to in-memory.
    """
    global _qa_job_store
    if _qa_job_store is None:
        # Check if MongoDB should be used
        use_mongo = os.getenv("JOB_STORE_BACKEND", "mongo").lower() == "mongo"
        if use_mongo:
            _qa_job_store = MongoQAJobStore()
            logger.info("Using MongoDB QA job store")
        else:
            _qa_job_store = InMemoryQAJobStore()
            logger.info("Using in-memory QA job store")
    return _qa_job_store


def set_qa_job_store(store: BaseQAJobStore) -> None:
    """Set the QA job store instance (for testing)."""
    global _qa_job_store
    _qa_job_store = store


# Convenience functions using default store
async def create_qa_job(project_id: str) -> str:
    """Create a new QA job using the default store."""
    return await get_qa_job_store().create_job(project_id)


async def get_qa_job(job_id: str) -> Optional[QAJob]:
    """Get a QA job by ID using the default store."""
    return await get_qa_job_store().get_job(job_id)


async def update_qa_job(job_id: str, **updates) -> Optional[QAJob]:
    """Update a QA job using the default store."""
    return await get_qa_job_store().update_job(job_id, **updates)


async def get_qa_job_for_project(project_id: str) -> Optional[QAJob]:
    """Get the most recent QA job for a project."""
    return await get_qa_job_store().get_job_for_project(project_id)
