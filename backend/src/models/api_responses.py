"""API response models for AI draft generation.

These models define the async job pattern for long-running generation:
1. POST /api/ai/draft/generate -> queued response with job_id
2. GET /api/ai/draft/status/:job_id -> progress updates
3. POST /api/ai/draft/cancel/:job_id -> cancellation

Pydantic v2. Extra fields are forbidden to prevent drift.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional, List

from pydantic import BaseModel, Field, ConfigDict

from .draft_plan import DraftPlan
from .visuals import VisualPlan


class JobStatus(str, Enum):
    """Status of a draft generation job."""
    queued = "queued"
    planning = "planning"
    generating = "generating"
    completed = "completed"
    cancelled = "cancelled"
    failed = "failed"


class GenerationProgress(BaseModel):
    """Progress information during generation."""
    model_config = ConfigDict(extra="forbid")

    current_chapter: int = Field(ge=0, description="Current chapter being generated (0 if not started)")
    total_chapters: int = Field(ge=0, description="Total chapters to generate")
    current_chapter_title: Optional[str] = Field(default=None, description="Title of current chapter")
    chapters_completed: int = Field(ge=0, default=0, description="Number of chapters completed")
    estimated_remaining_seconds: Optional[int] = Field(
        default=None,
        ge=0,
        description="Estimated seconds remaining"
    )


class TokenUsage(BaseModel):
    """Token usage statistics for a generation."""
    model_config = ConfigDict(extra="forbid")

    prompt_tokens: int = Field(ge=0, description="Input tokens used")
    completion_tokens: int = Field(ge=0, description="Output tokens generated")
    total_tokens: int = Field(ge=0, description="Total tokens used")


class GenerationStats(BaseModel):
    """Statistics about the completed generation."""
    model_config = ConfigDict(extra="forbid")

    chapters_generated: int = Field(ge=0, description="Number of chapters generated")
    total_words: int = Field(ge=0, description="Total word count of draft")
    generation_time_ms: int = Field(ge=0, description="Total generation time in milliseconds")
    tokens_used: TokenUsage = Field(description="Token usage breakdown")


class DraftGenerateRequest(BaseModel):
    """Request body for draft generation."""
    model_config = ConfigDict(extra="forbid")

    transcript: str = Field(min_length=500, description="Source transcript (min 500 chars)")
    outline: List[dict] = Field(min_length=3, description="Outline items (min 3)")
    resources: List[dict] = Field(default_factory=list, description="Optional resources")
    style_config: dict = Field(description="StyleConfig or StyleConfigEnvelope")


class DraftGenerateResponse(BaseModel):
    """Response for POST /api/ai/draft/generate.

    Returns immediately with job_id for polling.
    If generation is fast enough, may return completed result directly.
    """
    model_config = ConfigDict(extra="forbid")

    job_id: str = Field(description="Unique job identifier for polling")
    status: JobStatus = Field(description="Current job status")
    progress: Optional[GenerationProgress] = Field(
        default=None,
        description="Progress info (if generating)"
    )

    # Only present when status == completed
    draft_markdown: Optional[str] = Field(
        default=None,
        description="Generated markdown (only when completed)"
    )
    draft_plan: Optional[DraftPlan] = Field(
        default=None,
        description="Generation plan (only when completed)"
    )
    visual_plan: Optional[VisualPlan] = Field(
        default=None,
        description="Visual opportunities (only when completed)"
    )
    generation_stats: Optional[GenerationStats] = Field(
        default=None,
        description="Generation statistics (only when completed)"
    )

    # Error info (only when status == failed)
    error: Optional[str] = Field(
        default=None,
        description="Error message (only when failed)"
    )
    error_code: Optional[str] = Field(
        default=None,
        description="Error code for programmatic handling"
    )


class DraftStatusResponse(BaseModel):
    """Response for GET /api/ai/draft/status/:job_id.

    Used for polling job progress.
    """
    model_config = ConfigDict(extra="forbid")

    job_id: str = Field(description="Job identifier")
    status: JobStatus = Field(description="Current job status")
    progress: Optional[GenerationProgress] = Field(
        default=None,
        description="Progress info (if generating)"
    )

    # Only present when status == completed
    draft_markdown: Optional[str] = Field(
        default=None,
        description="Generated markdown (only when completed)"
    )
    draft_plan: Optional[DraftPlan] = Field(
        default=None,
        description="Generation plan (only when completed)"
    )
    visual_plan: Optional[VisualPlan] = Field(
        default=None,
        description="Visual opportunities (only when completed)"
    )
    generation_stats: Optional[GenerationStats] = Field(
        default=None,
        description="Generation statistics (only when completed)"
    )

    # Partial results (if cancelled mid-generation)
    partial_draft_markdown: Optional[str] = Field(
        default=None,
        description="Partial draft if cancelled mid-generation"
    )
    chapters_available: Optional[int] = Field(
        default=None,
        description="Number of chapters available in partial draft"
    )

    # Error info
    error: Optional[str] = Field(
        default=None,
        description="Error message (only when failed)"
    )
    error_code: Optional[str] = Field(
        default=None,
        description="Error code for programmatic handling"
    )


class DraftCancelResponse(BaseModel):
    """Response for POST /api/ai/draft/cancel/:job_id."""
    model_config = ConfigDict(extra="forbid")

    job_id: str = Field(description="Job identifier")
    status: JobStatus = Field(description="Job status after cancellation")
    cancelled: bool = Field(description="Whether cancellation was successful")
    message: str = Field(description="Human-readable status message")

    # Partial results if available
    partial_draft_markdown: Optional[str] = Field(
        default=None,
        description="Partial draft if chapters were completed"
    )
    chapters_available: Optional[int] = Field(
        default=None,
        description="Number of chapters available"
    )


class DraftRegenerateRequest(BaseModel):
    """Request body for section regeneration."""
    model_config = ConfigDict(extra="forbid")

    section_outline_item_id: str = Field(description="Outline item ID to regenerate")
    draft_plan: dict = Field(description="Original DraftPlan")
    existing_draft: str = Field(description="Current full markdown draft")
    style_config: dict = Field(description="StyleConfig or StyleConfigEnvelope")


class DraftRegenerateResponse(BaseModel):
    """Response for POST /api/ai/draft/regenerate."""
    model_config = ConfigDict(extra="forbid")

    section_markdown: str = Field(description="Regenerated section markdown")
    section_start_line: int = Field(ge=1, description="Start line in original draft")
    section_end_line: int = Field(ge=1, description="End line in original draft")
    generation_stats: Optional[GenerationStats] = Field(
        default=None,
        description="Generation statistics"
    )
    error: Optional[str] = Field(default=None, description="Error message if failed")
