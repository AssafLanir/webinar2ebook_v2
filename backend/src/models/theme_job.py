"""Theme proposal job model.

Used to track async theme proposal jobs.
"""

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict

from .edition import Theme


class ThemeJobStatus(str, Enum):
    """Status of theme proposal job."""

    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ThemeJob(BaseModel):
    """Theme proposal job.

    Tracks the status of async theme proposal generation.
    """

    model_config = ConfigDict(extra="forbid")

    job_id: str
    project_id: str
    status: ThemeJobStatus = ThemeJobStatus.QUEUED
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    themes: list[Theme] = []
    error: Optional[str] = None

    def is_terminal(self) -> bool:
        """Check if job is in a terminal state."""
        return self.status in (
            ThemeJobStatus.COMPLETED,
            ThemeJobStatus.FAILED,
            ThemeJobStatus.CANCELLED,
        )
