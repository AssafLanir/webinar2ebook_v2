"""API response models for AI draft generation.

These models define the async job pattern for long-running generation:
1. POST /api/ai/draft/generate -> queued response with job_id
2. GET /api/ai/draft/status/:job_id -> progress updates
3. POST /api/ai/draft/cancel/:job_id -> cancellation

All responses use the standard { data, error } envelope pattern.

Pydantic v2. Extra fields are forbidden to prevent drift.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional, List, Generic, TypeVar

from pydantic import BaseModel, Field, ConfigDict

from .draft_plan import DraftPlan
from .visuals import VisualPlan

T = TypeVar("T")


class JobStatus(str, Enum):
    """Status of a draft generation job."""
    queued = "queued"
    planning = "planning"
    evidence_map = "evidence_map"  # NEW: Evidence Map extraction phase (Spec 009)
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


# ============================================================================
# Request Models
# ============================================================================

class DraftGenerateRequest(BaseModel):
    """Request body for draft generation.

    Note: Validation (transcript >= 500 chars, outline >= 3 items) is done
    in the endpoint to return proper { data, error } envelope responses.
    """
    model_config = ConfigDict(extra="forbid")

    transcript: str = Field(description="Source transcript (min 500 chars)")
    outline: List[dict] = Field(description="Outline items (min 3)")
    resources: List[dict] = Field(default_factory=list, description="Optional resources")
    style_config: dict = Field(description="StyleConfig or StyleConfigEnvelope")
    candidate_count: int = Field(
        default=1,
        ge=1,
        le=5,
        description="Number of candidates for best-of-N selection (1=disabled, 2-3 recommended)"
    )


class DraftRegenerateRequest(BaseModel):
    """Request body for section regeneration."""
    model_config = ConfigDict(extra="forbid")

    section_outline_item_id: str = Field(description="Outline item ID to regenerate")
    draft_plan: dict = Field(description="Original DraftPlan")
    existing_draft: str = Field(description="Current full markdown draft")
    style_config: dict = Field(description="StyleConfig or StyleConfigEnvelope")


# ============================================================================
# Response Data Models (inner payload, NOT the envelope)
# ============================================================================

class DraftGenerateData(BaseModel):
    """Data payload for POST /api/ai/draft/generate response.

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


class DraftStatusData(BaseModel):
    """Data payload for GET /api/ai/draft/status/:job_id response.

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

    # Error details (if failed)
    error_code: Optional[str] = Field(
        default=None,
        description="Machine-readable error code (only when failed)"
    )
    error_message: Optional[str] = Field(
        default=None,
        description="Human-readable error message (only when failed)"
    )

    # Evidence Map info (Spec 009)
    evidence_map_summary: Optional[dict] = Field(
        default=None,
        description="Summary of Evidence Map (claims per chapter, content mode)"
    )
    constraint_warnings: Optional[List[str]] = Field(
        default=None,
        description="Warnings about content mode constraints"
    )


class DraftCancelData(BaseModel):
    """Data payload for POST /api/ai/draft/cancel/:job_id response."""
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


class DraftRegenerateData(BaseModel):
    """Data payload for POST /api/ai/draft/regenerate response."""
    model_config = ConfigDict(extra="forbid")

    section_markdown: str = Field(description="Regenerated section markdown")
    section_start_line: int = Field(ge=1, description="Start line in original draft")
    section_end_line: int = Field(ge=1, description="End line in original draft")
    generation_stats: Optional[GenerationStats] = Field(
        default=None,
        description="Generation statistics"
    )


# ============================================================================
# Envelope Models (standard { data, error } pattern)
# ============================================================================

class ErrorDetail(BaseModel):
    """Error detail structure for API responses."""
    model_config = ConfigDict(extra="forbid")

    code: str = Field(description="Machine-readable error code")
    message: str = Field(description="Human-readable error message")


class DraftGenerateResponse(BaseModel):
    """Envelope for POST /api/ai/draft/generate response."""
    model_config = ConfigDict(extra="forbid")

    data: Optional[DraftGenerateData] = Field(default=None, description="Response data on success")
    error: Optional[ErrorDetail] = Field(default=None, description="Error details on failure")


class DraftStatusResponse(BaseModel):
    """Envelope for GET /api/ai/draft/status/:job_id response."""
    model_config = ConfigDict(extra="forbid")

    data: Optional[DraftStatusData] = Field(default=None, description="Response data on success")
    error: Optional[ErrorDetail] = Field(default=None, description="Error details on failure")


class DraftCancelResponse(BaseModel):
    """Envelope for POST /api/ai/draft/cancel/:job_id response."""
    model_config = ConfigDict(extra="forbid")

    data: Optional[DraftCancelData] = Field(default=None, description="Response data on success")
    error: Optional[ErrorDetail] = Field(default=None, description="Error details on failure")


class DraftRegenerateResponse(BaseModel):
    """Envelope for POST /api/ai/draft/regenerate response."""
    model_config = ConfigDict(extra="forbid")

    data: Optional[DraftRegenerateData] = Field(default=None, description="Response data on success")
    error: Optional[ErrorDetail] = Field(default=None, description="Error details on failure")


# ============================================================================
# Export API Response Models (Spec 006)
# ============================================================================

from .export_job import ExportJobStatus


class PreviewData(BaseModel):
    """Data payload for GET /api/projects/{id}/ebook/preview response."""
    model_config = ConfigDict(extra="forbid")

    html: str = Field(description="Complete HTML document with embedded styles")


class PreviewResponse(BaseModel):
    """Envelope for GET /api/projects/{id}/ebook/preview response."""
    model_config = ConfigDict(extra="forbid")

    data: Optional[PreviewData] = Field(default=None, description="Response data on success")
    error: Optional[ErrorDetail] = Field(default=None, description="Error details on failure")


class ExportStartData(BaseModel):
    """Data payload for POST /api/projects/{id}/ebook/export response."""
    model_config = ConfigDict(extra="forbid")

    job_id: str = Field(description="UUID of the created export job")


class ExportStartResponse(BaseModel):
    """Envelope for POST /api/projects/{id}/ebook/export response."""
    model_config = ConfigDict(extra="forbid")

    data: Optional[ExportStartData] = Field(default=None, description="Response data on success")
    error: Optional[ErrorDetail] = Field(default=None, description="Error details on failure")


class ExportStatusData(BaseModel):
    """Data payload for GET /api/projects/{id}/ebook/export/status/{job_id} response."""
    model_config = ConfigDict(extra="forbid")

    job_id: str = Field(description="Job identifier")
    status: ExportJobStatus = Field(description="Current export job status")
    progress: int = Field(ge=0, le=100, description="Progress percentage (0-100)")
    download_url: Optional[str] = Field(
        default=None,
        description="Download URL when status is 'completed', null otherwise"
    )
    error_message: Optional[str] = Field(
        default=None,
        description="Error message when status is 'failed', null otherwise"
    )


class ExportStatusResponse(BaseModel):
    """Envelope for GET /api/projects/{id}/ebook/export/status/{job_id} response."""
    model_config = ConfigDict(extra="forbid")

    data: Optional[ExportStatusData] = Field(default=None, description="Response data on success")
    error: Optional[ErrorDetail] = Field(default=None, description="Error details on failure")


class ExportCancelData(BaseModel):
    """Data payload for POST /api/projects/{id}/ebook/export/cancel/{job_id} response."""
    model_config = ConfigDict(extra="forbid")

    cancelled: bool = Field(description="True if cancellation was successful")


class ExportCancelResponse(BaseModel):
    """Envelope for POST /api/projects/{id}/ebook/export/cancel/{job_id} response."""
    model_config = ConfigDict(extra="forbid")

    data: Optional[ExportCancelData] = Field(default=None, description="Response data on success")
    error: Optional[ErrorDetail] = Field(default=None, description="Error details on failure")


# ============================================================================
# Legacy aliases for backward compatibility
# (Tests may use these directly - keeping them as aliases)
# ============================================================================

# Note: These are kept for backward compatibility but new code should use
# the *Data models for inner payload and *Response for envelopes
