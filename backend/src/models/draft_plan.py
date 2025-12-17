"""Draft plan models for structured AI generation.

Design goal:
- DraftPlan reduces hallucinations and enables chunked generation
- Confirms intended chapter list and scope before writing
- Maps transcript segments to chapters for focused generation
- Enables regeneration of individual sections with correct context

Pydantic v2. Extra fields are forbidden to prevent drift.
"""

from __future__ import annotations

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, ConfigDict

from .visuals import VisualPlan


class TranscriptRelevance(str, Enum):
    """How relevant a transcript segment is to a chapter."""
    primary = "primary"
    supporting = "supporting"
    reference = "reference"


class TranscriptSegment(BaseModel):
    """A mapped segment of the source transcript."""
    model_config = ConfigDict(extra="forbid")

    start_char: int = Field(ge=0, description="Starting character index in transcript")
    end_char: int = Field(ge=0, description="Ending character index in transcript")
    relevance: TranscriptRelevance = Field(
        default=TranscriptRelevance.primary,
        description="How this segment relates to the chapter"
    )


class ChapterPlan(BaseModel):
    """Plan for generating a single chapter."""
    model_config = ConfigDict(extra="forbid")

    chapter_number: int = Field(ge=1, description="1-based chapter number")
    title: str = Field(description="Chapter title")
    outline_item_id: str = Field(description="Reference to source outline item")
    goals: List[str] = Field(
        default_factory=list,
        description="2-4 learning objectives for this chapter"
    )
    key_points: List[str] = Field(
        default_factory=list,
        description="3-6 main points to cover"
    )
    transcript_segments: List[TranscriptSegment] = Field(
        default_factory=list,
        description="Mapped transcript portions for this chapter"
    )
    estimated_words: int = Field(
        default=1500,
        ge=100,
        description="Estimated word count for this chapter"
    )


class GenerationMetadata(BaseModel):
    """Metadata about the generation plan."""
    model_config = ConfigDict(extra="forbid")

    estimated_total_words: int = Field(
        ge=0,
        description="Total estimated word count for the ebook"
    )
    estimated_generation_time_seconds: int = Field(
        ge=0,
        description="Estimated time to generate all chapters"
    )
    transcript_utilization: float = Field(
        ge=0.0,
        le=1.0,
        description="Fraction of transcript content used (0.0-1.0)"
    )


class DraftPlan(BaseModel):
    """The complete generation plan for an ebook draft.

    Generated before actual chapter content is written.
    Enables chunked generation and regeneration of sections.
    """
    model_config = ConfigDict(extra="forbid")

    version: int = Field(default=1, ge=1, description="Schema version for migrations")
    book_title: str = Field(description="Title of the generated ebook")
    chapters: List[ChapterPlan] = Field(
        default_factory=list,
        description="Planned chapters with mapped content"
    )
    visual_plan: VisualPlan = Field(
        default_factory=VisualPlan,
        description="Visual opportunities generated alongside the plan"
    )
    generation_metadata: GenerationMetadata = Field(
        description="Metadata about the generation plan"
    )


DRAFT_PLAN_VERSION = 1
"""Current version of the DraftPlan schema."""


def draft_plan_json_schema() -> dict:
    """Return JSON schema for DraftPlan (for OpenAPI docs)."""
    return DraftPlan.model_json_schema()
