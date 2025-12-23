"""Job store for PDF export jobs.

Supports two backends:
1. MongoDB (durable) - jobs survive server restart
2. In-memory (fallback) - for testing or when MongoDB unavailable

Features:
- TTL cleanup (1-hour default) via MongoDB TTL index or periodic task
- Thread-safe operations via asyncio locks
- Simple CRUD operations

This follows the same pattern as job_store.py for GenerationJob,
but uses ExportJob model and a separate collection.
"""

from __future__ import annotations

import asyncio
import logging
import os
from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import uuid4

from src.models import ExportJob, ExportJobStatus, ExportFormat

logger = logging.getLogger(__name__)

# Default TTL for completed/failed jobs (1 hour)
DEFAULT_JOB_TTL_SECONDS = 3600

# How often to run cleanup (5 minutes)
CLEANUP_INTERVAL_SECONDS = 300

# Collection name for MongoDB storage
EXPORT_JOBS_COLLECTION = "export_jobs"


class BaseExportJobStore(ABC):
    """Abstract base class for export job stores.

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
    async def create_job(self, project_id: str, format: ExportFormat = ExportFormat.pdf) -> str:
        """Create a new export job."""
        pass

    @abstractmethod
    async def get_job(self, job_id: str) -> Optional[ExportJob]:
        """Get a job by ID."""
        pass

    @abstractmethod
    async def update_job(self, job_id: str, **updates) -> Optional[ExportJob]:
        """Update a job's fields."""
        pass

    @abstractmethod
    async def delete_job(self, job_id: str) -> bool:
        """Delete a job."""
        pass

    @abstractmethod
    async def list_jobs(
        self,
        project_id: Optional[str] = None,
        status: Optional[ExportJobStatus] = None,
        limit: int = 100,
    ) -> list[ExportJob]:
        """List jobs with optional filtering."""
        pass


class InMemoryExportJobStore(BaseExportJobStore):
    """In-memory export job store with TTL cleanup.

    Thread-safe via asyncio locks for concurrent access.
    Jobs are lost on server restart.
    """

    def __init__(self, ttl_seconds: int = DEFAULT_JOB_TTL_SECONDS):
        """Initialize job store."""
        self._jobs: dict[str, ExportJob] = {}
        self._lock = asyncio.Lock()
        self._ttl_seconds = ttl_seconds
        self._cleanup_task: Optional[asyncio.Task] = None

    async def start_cleanup_task(self) -> None:
        """Start the background cleanup task."""
        if self._cleanup_task is None or self._cleanup_task.done():
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())
            logger.info("Export job store cleanup task started")

    async def stop_cleanup_task(self) -> None:
        """Stop the background cleanup task."""
        if self._cleanup_task and not self._cleanup_task.done():
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            logger.info("Export job store cleanup task stopped")

    async def _cleanup_loop(self) -> None:
        """Periodically clean up expired jobs."""
        while True:
            try:
                await asyncio.sleep(CLEANUP_INTERVAL_SECONDS)
                await self.cleanup_expired_jobs()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in export job cleanup loop: {e}")

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
                logger.info(f"Cleaned up {len(expired_ids)} expired export jobs")

            return len(expired_ids)

    async def create_job(self, project_id: str, format: ExportFormat = ExportFormat.pdf) -> str:
        """Create a new export job."""
        job_id = str(uuid4())
        job = ExportJob(
            job_id=job_id,
            project_id=project_id,
            format=format,
            status=ExportJobStatus.pending,
            created_at=datetime.now(timezone.utc),
        )

        async with self._lock:
            self._jobs[job_id] = job

        logger.debug(f"Created export job {job_id}")
        return job_id

    async def get_job(self, job_id: str) -> Optional[ExportJob]:
        """Get a job by ID."""
        async with self._lock:
            return self._jobs.get(job_id)

    async def update_job(self, job_id: str, **updates) -> Optional[ExportJob]:
        """Update a job's fields."""
        async with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return None

            for key, value in updates.items():
                if hasattr(job, key):
                    setattr(job, key, value)
                else:
                    logger.warning(f"Unknown field {key} for export job update")

            # Auto-set timestamps
            if updates.get("status") == ExportJobStatus.processing and not job.started_at:
                job.started_at = datetime.now(timezone.utc)
            if updates.get("status") in (
                ExportJobStatus.completed,
                ExportJobStatus.cancelled,
                ExportJobStatus.failed,
            ):
                job.completed_at = datetime.now(timezone.utc)

            return job

    async def delete_job(self, job_id: str) -> bool:
        """Delete a job."""
        async with self._lock:
            if job_id in self._jobs:
                del self._jobs[job_id]
                logger.debug(f"Deleted export job {job_id}")
                return True
            return False

    async def list_jobs(
        self,
        project_id: Optional[str] = None,
        status: Optional[ExportJobStatus] = None,
        limit: int = 100,
    ) -> list[ExportJob]:
        """List jobs with optional filtering."""
        async with self._lock:
            jobs = list(self._jobs.values())
            if project_id:
                jobs = [j for j in jobs if j.project_id == project_id]
            if status:
                jobs = [j for j in jobs if j.status == status]
            jobs.sort(key=lambda j: j.created_at, reverse=True)
            return jobs[:limit]

    async def count_active_jobs(self, project_id: Optional[str] = None) -> int:
        """Count jobs that are currently running."""
        async with self._lock:
            jobs = list(self._jobs.values())
            if project_id:
                jobs = [j for j in jobs if j.project_id == project_id]
            return sum(1 for job in jobs if not job.is_terminal())

    def __len__(self) -> int:
        """Return total number of jobs in store."""
        return len(self._jobs)


class MongoExportJobStore(BaseExportJobStore):
    """MongoDB-backed export job store with TTL index.

    Jobs persist across server restarts.
    Uses MongoDB TTL index for automatic cleanup (no background task needed).
    """

    def __init__(self, ttl_seconds: int = DEFAULT_JOB_TTL_SECONDS):
        """Initialize MongoDB export job store."""
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
        return db[EXPORT_JOBS_COLLECTION]

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
            # Create index on project_id for filtering
            await collection.create_index("project_id")
            # Create index on status for filtering
            await collection.create_index("status")
            self._index_created = True
            logger.info("MongoDB export job store indexes created")
        except Exception as e:
            logger.warning(f"Failed to create MongoDB export job indexes: {e}")

    def _job_to_doc(self, job: ExportJob) -> dict:
        """Convert ExportJob to MongoDB document."""
        doc = {
            "job_id": job.job_id,
            "project_id": job.project_id,
            "format": job.format.value,
            "status": job.status.value,
            "progress": job.progress,
            "created_at": job.created_at,
            "started_at": job.started_at,
            "completed_at": job.completed_at,
            "result_path": job.result_path,
            "download_filename": job.download_filename,
            "error_message": job.error_message,
            "cancel_requested": job.cancel_requested,
        }

        # Set expires_at for TTL cleanup
        if job.is_terminal() and job.completed_at:
            doc["expires_at"] = job.completed_at + timedelta(seconds=self._ttl_seconds)
        else:
            doc["expires_at"] = None

        return doc

    def _doc_to_job(self, doc: dict) -> ExportJob:
        """Convert MongoDB document to ExportJob."""
        return ExportJob(
            job_id=doc["job_id"],
            project_id=doc["project_id"],
            format=ExportFormat(doc["format"]),
            status=ExportJobStatus(doc["status"]),
            progress=doc.get("progress", 0),
            created_at=doc["created_at"],
            started_at=doc.get("started_at"),
            completed_at=doc.get("completed_at"),
            result_path=doc.get("result_path"),
            download_filename=doc.get("download_filename"),
            error_message=doc.get("error_message"),
            cancel_requested=doc.get("cancel_requested", False),
        )

    async def create_job(self, project_id: str, format: ExportFormat = ExportFormat.pdf) -> str:
        """Create a new export job in MongoDB."""
        await self.ensure_indexes()

        job_id = str(uuid4())
        job = ExportJob(
            job_id=job_id,
            project_id=project_id,
            format=format,
            status=ExportJobStatus.pending,
            created_at=datetime.now(timezone.utc),
        )

        collection = await self._get_collection()
        doc = self._job_to_doc(job)
        await collection.insert_one(doc)

        logger.debug(f"Created export job {job_id} in MongoDB")
        return job_id

    async def get_job(self, job_id: str) -> Optional[ExportJob]:
        """Get a job by ID from MongoDB."""
        collection = await self._get_collection()
        doc = await collection.find_one({"job_id": job_id})

        if not doc:
            return None

        return self._doc_to_job(doc)

    async def update_job(self, job_id: str, **updates) -> Optional[ExportJob]:
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
                logger.warning(f"Unknown field {key} for export job update")

        # Auto-set timestamps
        if updates.get("status") == ExportJobStatus.processing and not job.started_at:
            job.started_at = datetime.now(timezone.utc)
        if updates.get("status") in (
            ExportJobStatus.completed,
            ExportJobStatus.cancelled,
            ExportJobStatus.failed,
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
            logger.debug(f"Deleted export job {job_id} from MongoDB")

        return deleted

    async def list_jobs(
        self,
        project_id: Optional[str] = None,
        status: Optional[ExportJobStatus] = None,
        limit: int = 100,
    ) -> list[ExportJob]:
        """List jobs with optional filtering."""
        collection = await self._get_collection()

        query: dict = {}
        if project_id:
            query["project_id"] = project_id
        if status:
            query["status"] = status.value

        cursor = collection.find(query).sort("created_at", -1).limit(limit)
        docs = await cursor.to_list(length=limit)

        return [self._doc_to_job(doc) for doc in docs]

    async def count_active_jobs(self, project_id: Optional[str] = None) -> int:
        """Count jobs that are currently running."""
        collection = await self._get_collection()
        query: dict = {
            "status": {"$in": [
                ExportJobStatus.pending.value,
                ExportJobStatus.processing.value,
            ]}
        }
        if project_id:
            query["project_id"] = project_id
        count = await collection.count_documents(query)
        return count


# Module-level singleton instance
_default_store: Optional[BaseExportJobStore] = None


def get_export_job_store() -> BaseExportJobStore:
    """Get the default export job store singleton.

    Uses MongoDB if available, falls back to in-memory.
    """
    global _default_store
    if _default_store is None:
        # Check if MongoDB should be used
        use_mongo = os.getenv("JOB_STORE_BACKEND", "mongo").lower() == "mongo"
        if use_mongo:
            _default_store = MongoExportJobStore()
            logger.info("Using MongoDB export job store")
        else:
            _default_store = InMemoryExportJobStore()
            logger.info("Using in-memory export job store")
    return _default_store


def set_export_job_store(store: BaseExportJobStore) -> None:
    """Set the export job store instance (for testing)."""
    global _default_store
    _default_store = store


# Convenience functions for direct access
async def create_export_job(project_id: str, format: ExportFormat = ExportFormat.pdf) -> str:
    """Create a new export job using the default store."""
    return await get_export_job_store().create_job(project_id=project_id, format=format)


async def get_export_job(job_id: str) -> Optional[ExportJob]:
    """Get an export job by ID using the default store."""
    return await get_export_job_store().get_job(job_id)


async def update_export_job(job_id: str, **updates) -> Optional[ExportJob]:
    """Update an export job using the default store."""
    return await get_export_job_store().update_job(job_id, **updates)


async def delete_export_job(job_id: str) -> bool:
    """Delete an export job using the default store."""
    return await get_export_job_store().delete_job(job_id)
