"""QA Job model for async quality analysis.

This model tracks the state of a QA analysis job.
Similar to GenerationJob but simpler (no chapter progress).

Pydantic v2. Extra fields are forbidden to prevent drift.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, ConfigDict

from .qa_report import QAReport


class QAJobStatus(str, Enum):
    """Status of a QA analysis job."""
    queued = "queued"          # Job created, waiting to start
    running = "running"        # Analysis in progress
    completed = "completed"    # Analysis complete, report available
    failed = "failed"          # Analysis failed
    cancelled = "cancelled"    # Job was cancelled


def _utcnow() -> datetime:
    """Return timezone-aware UTC now."""
    return datetime.now(timezone.utc)


class QAJob(BaseModel):
    """State for a QA analysis job.

    Tracks progress, results, and error state.
    Simpler than GenerationJob since QA doesn't have chapter-by-chapter progress.
    """
    model_config = ConfigDict(extra="forbid")

    # Identity
    job_id: str = Field(description="UUID identifier for this job")
    project_id: str = Field(description="Associated project ID")

    # Status
    status: QAJobStatus = Field(
        default=QAJobStatus.queued,
        description="Current job status"
    )

    # Timestamps
    created_at: datetime = Field(
        default_factory=_utcnow,
        description="Job creation timestamp"
    )
    started_at: Optional[datetime] = Field(
        default=None,
        description="When analysis actually started"
    )
    completed_at: Optional[datetime] = Field(
        default=None,
        description="When analysis completed/failed/cancelled"
    )

    # Progress (simple percentage)
    progress_pct: int = Field(
        default=0,
        ge=0,
        le=100,
        description="Progress percentage (0-100)"
    )
    current_stage: Optional[str] = Field(
        default=None,
        description="Current analysis stage (structural, semantic, etc.)"
    )

    # Results
    report: Optional[QAReport] = Field(
        default=None,
        description="QA report (available when completed)"
    )

    # Error handling
    error: Optional[str] = Field(
        default=None,
        description="Error message if job failed"
    )
    error_code: Optional[str] = Field(
        default=None,
        description="Machine-readable error code"
    )

    # Control
    cancel_requested: bool = Field(
        default=False,
        description="Set to True to request cancellation"
    )

    def is_terminal(self) -> bool:
        """Check if job is in a terminal state (no more updates expected)."""
        return self.status in (
            QAJobStatus.completed,
            QAJobStatus.cancelled,
            QAJobStatus.failed,
        )

    def mark_started(self) -> None:
        """Mark job as started."""
        self.status = QAJobStatus.running
        self.started_at = _utcnow()

    def mark_completed(self, report: QAReport) -> None:
        """Mark job as completed with report."""
        self.status = QAJobStatus.completed
        self.completed_at = _utcnow()
        self.progress_pct = 100
        self.report = report

    def mark_failed(self, error: str, error_code: Optional[str] = None) -> None:
        """Mark job as failed with error."""
        self.status = QAJobStatus.failed
        self.completed_at = _utcnow()
        self.error = error
        self.error_code = error_code

    def mark_cancelled(self) -> None:
        """Mark job as cancelled."""
        self.status = QAJobStatus.cancelled
        self.completed_at = _utcnow()

    def update_progress(self, pct: int, stage: Optional[str] = None) -> None:
        """Update progress percentage and optionally the stage."""
        self.progress_pct = max(0, min(100, pct))
        if stage:
            self.current_stage = stage
