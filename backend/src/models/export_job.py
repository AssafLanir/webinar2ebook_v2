"""Export job model for async PDF/EPUB export.

This model tracks the state of an export job (PDF or EPUB generation).
Used by the export job store for job management with TTL cleanup.

Pydantic v2. Extra fields are forbidden to prevent drift.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, ConfigDict


def _utcnow() -> datetime:
    """Return timezone-aware UTC now."""
    return datetime.now(timezone.utc)


class ExportFormat(str, Enum):
    """Supported export formats."""
    pdf = "pdf"
    epub = "epub"


class ExportJobStatus(str, Enum):
    """Export job status values."""
    pending = "pending"        # Job created, not started
    processing = "processing"  # PDF generation in progress
    completed = "completed"    # PDF ready for download
    failed = "failed"          # Generation failed
    cancelled = "cancelled"    # User cancelled


class ExportJob(BaseModel):
    """State for an export job (PDF generation).

    Tracks progress, results, and cancellation state.
    Used by export_job_store.py for managing active export jobs.
    """
    model_config = ConfigDict(extra="forbid")

    # Identity
    job_id: str = Field(description="UUID identifier for this job")
    project_id: str = Field(description="Associated project ID")

    # Configuration
    format: ExportFormat = Field(
        default=ExportFormat.pdf,
        description="Export format"
    )

    # Status
    status: ExportJobStatus = Field(
        default=ExportJobStatus.pending,
        description="Current job status"
    )
    progress: int = Field(
        default=0,
        ge=0,
        le=100,
        description="Progress percentage (0-100)"
    )

    # Timestamps
    created_at: datetime = Field(
        default_factory=_utcnow,
        description="Job creation timestamp"
    )
    started_at: Optional[datetime] = Field(
        default=None,
        description="When export actually started"
    )
    completed_at: Optional[datetime] = Field(
        default=None,
        description="When export completed/failed/cancelled"
    )

    # Results
    result_path: Optional[str] = Field(
        default=None,
        description="Path to generated file (if completed)"
    )
    download_filename: Optional[str] = Field(
        default=None,
        description="Sanitized filename for download"
    )

    # Error handling
    error_message: Optional[str] = Field(
        default=None,
        description="Error details if job failed"
    )

    # Control
    cancel_requested: bool = Field(
        default=False,
        description="Set to True to request cancellation"
    )

    def is_terminal(self) -> bool:
        """Check if job is in a terminal state (no more updates expected)."""
        return self.status in (
            ExportJobStatus.completed,
            ExportJobStatus.cancelled,
            ExportJobStatus.failed,
        )

    def get_download_url(self, project_id: str) -> Optional[str]:
        """Get download URL if job is completed."""
        if self.status == ExportJobStatus.completed:
            return f"/api/projects/{project_id}/ebook/export/download/{self.job_id}"
        return None
