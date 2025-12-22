"""Generation job model for async draft generation.

This model tracks the state of a draft generation job.
Used by the job store for in-memory job management with TTL cleanup.

Pydantic v2. Extra fields are forbidden to prevent drift.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional, List

from pydantic import BaseModel, Field, ConfigDict


def _utcnow() -> datetime:
    """Return timezone-aware UTC now."""
    return datetime.now(timezone.utc)


def _ensure_tz_aware(dt: Optional[datetime]) -> Optional[datetime]:
    """Ensure datetime is timezone-aware (assume UTC if naive)."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt

from .api_responses import JobStatus, GenerationProgress, GenerationStats, TokenUsage
from .draft_plan import DraftPlan
from .visuals import VisualPlan


class GenerationJob(BaseModel):
    """In-memory state for a draft generation job.

    Tracks progress, results, and cancellation state.
    Used by job_store.py for managing active generation jobs.
    """
    model_config = ConfigDict(extra="forbid")

    # Identity
    job_id: str = Field(description="UUID identifier for this job")
    project_id: Optional[str] = Field(
        default=None,
        description="Associated project ID (if applicable)"
    )

    # Status
    status: JobStatus = Field(
        default=JobStatus.queued,
        description="Current job status"
    )
    created_at: datetime = Field(
        default_factory=_utcnow,
        description="Job creation timestamp"
    )

    # Progress tracking
    current_chapter: int = Field(
        default=0,
        ge=0,
        description="Chapter currently being generated (0 if not started)"
    )
    total_chapters: int = Field(
        default=0,
        ge=0,
        description="Total number of chapters to generate"
    )
    chapters_completed: List[str] = Field(
        default_factory=list,
        description="Markdown content for each completed chapter"
    )

    # Results
    draft_plan: Optional[DraftPlan] = Field(
        default=None,
        description="Generated DraftPlan (available after planning phase)"
    )
    visual_plan: Optional[VisualPlan] = Field(
        default=None,
        description="Generated VisualPlan (extracted from DraftPlan)"
    )
    draft_markdown: Optional[str] = Field(
        default=None,
        description="Final assembled markdown (available when completed)"
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
        description="Set to True to request cancellation after current chapter"
    )

    # Statistics tracking
    started_at: Optional[datetime] = Field(
        default=None,
        description="When generation actually started"
    )
    completed_at: Optional[datetime] = Field(
        default=None,
        description="When generation completed/failed/cancelled"
    )
    total_prompt_tokens: int = Field(
        default=0,
        ge=0,
        description="Accumulated prompt tokens used"
    )
    total_completion_tokens: int = Field(
        default=0,
        ge=0,
        description="Accumulated completion tokens used"
    )

    def get_progress(self) -> GenerationProgress:
        """Get current progress as GenerationProgress model."""
        chapters_done = len(self.chapters_completed)
        return GenerationProgress(
            current_chapter=self.current_chapter,
            total_chapters=self.total_chapters,
            current_chapter_title=self._get_current_chapter_title(),
            chapters_completed=chapters_done,
            estimated_remaining_seconds=self._estimate_remaining_seconds(),
        )

    def get_stats(self) -> GenerationStats:
        """Get generation statistics after completion."""
        total_words = sum(
            len(ch.split()) for ch in self.chapters_completed
        )
        generation_time_ms = 0
        if self.started_at and self.completed_at:
            # Ensure both are timezone-aware for comparison
            started = _ensure_tz_aware(self.started_at)
            completed = _ensure_tz_aware(self.completed_at)
            delta = completed - started  # type: ignore
            generation_time_ms = int(delta.total_seconds() * 1000)

        return GenerationStats(
            chapters_generated=len(self.chapters_completed),
            total_words=total_words,
            generation_time_ms=generation_time_ms,
            tokens_used=TokenUsage(
                prompt_tokens=self.total_prompt_tokens,
                completion_tokens=self.total_completion_tokens,
                total_tokens=self.total_prompt_tokens + self.total_completion_tokens,
            ),
        )

    def _get_current_chapter_title(self) -> Optional[str]:
        """Get title of the chapter currently being generated."""
        if not self.draft_plan or self.current_chapter == 0:
            return None
        if self.current_chapter <= len(self.draft_plan.chapters):
            return self.draft_plan.chapters[self.current_chapter - 1].title
        return None

    def _estimate_remaining_seconds(self) -> Optional[int]:
        """Estimate remaining generation time based on current progress."""
        if not self.started_at or self.total_chapters == 0:
            return None

        chapters_done = len(self.chapters_completed)
        if chapters_done == 0:
            # Initial estimate: ~15 seconds per chapter
            return self.total_chapters * 15

        # Calculate based on actual elapsed time
        # Ensure datetime is timezone-aware for comparison
        started = _ensure_tz_aware(self.started_at)
        elapsed = (_utcnow() - started).total_seconds()  # type: ignore
        time_per_chapter = elapsed / chapters_done
        remaining_chapters = self.total_chapters - chapters_done
        return int(time_per_chapter * remaining_chapters)

    def is_terminal(self) -> bool:
        """Check if job is in a terminal state (no more updates expected)."""
        return self.status in (
            JobStatus.completed,
            JobStatus.cancelled,
            JobStatus.failed,
        )
