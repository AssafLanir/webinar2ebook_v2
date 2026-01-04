"""Evidence Map models for Evidence-Grounded Drafting (Spec 009).

The Evidence Map is generated before chapter content and ensures all claims
are grounded in transcript evidence.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, ConfigDict

from .style_config import ContentMode


class ClaimType(str, Enum):
    """Type of claim for appropriate handling."""
    factual = "factual"
    opinion = "opinion"
    recommendation = "recommendation"
    anecdote = "anecdote"
    definition = "definition"


class MustIncludePriority(str, Enum):
    """Priority level for must-include items."""
    critical = "critical"
    important = "important"
    optional = "optional"


class SupportQuote(BaseModel):
    """A quote from the transcript supporting a claim."""

    model_config = ConfigDict(extra="forbid")

    quote: str = Field(description="Exact quote from transcript")
    start_char: Optional[int] = Field(default=None, ge=0)
    end_char: Optional[int] = Field(default=None, ge=0)
    speaker: Optional[str] = None


class EvidenceEntry(BaseModel):
    """A single claim with its supporting transcript evidence."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(description="Unique identifier")
    claim: str = Field(description="The claim that can be made")
    support: List[SupportQuote] = Field(min_length=1)
    confidence: float = Field(ge=0, le=1, default=0.8)
    claim_type: ClaimType = Field(default=ClaimType.factual)


class MustIncludeItem(BaseModel):
    """Key point that must appear in chapter."""

    model_config = ConfigDict(extra="forbid")

    point: str
    priority: MustIncludePriority
    evidence_ids: List[str] = Field(default_factory=list)


class TranscriptRange(BaseModel):
    """Character range in transcript."""

    model_config = ConfigDict(extra="forbid")

    start_char: int = Field(ge=0)
    end_char: int = Field(ge=0)


class SpeakerInfo(BaseModel):
    """Speaker identified in transcript."""

    model_config = ConfigDict(extra="forbid")

    name: str
    role: Optional[str] = None
    mentioned_credentials: Optional[str] = None


class GlobalContext(BaseModel):
    """Cross-chapter context from transcript."""

    model_config = ConfigDict(extra="forbid")

    speakers: List[SpeakerInfo] = Field(default_factory=list)
    main_topics: List[str] = Field(default_factory=list)
    key_terms: List[str] = Field(default_factory=list)


class ChapterEvidence(BaseModel):
    """Evidence grounding for a single chapter."""

    model_config = ConfigDict(extra="forbid")

    chapter_index: int = Field(ge=1, description="1-based chapter index")
    chapter_title: str
    outline_item_id: Optional[str] = None
    claims: List[EvidenceEntry] = Field(default_factory=list)
    must_include: List[MustIncludeItem] = Field(default_factory=list)
    forbidden: List[str] = Field(
        default_factory=list,
        description="Content types forbidden in this chapter"
    )
    transcript_range: Optional[TranscriptRange] = None


class EvidenceMap(BaseModel):
    """Per-chapter grounding data for source-faithful generation."""

    model_config = ConfigDict(extra="forbid")

    version: int = Field(default=1, description="Schema version")
    project_id: str = Field(description="Associated project ID")
    content_mode: ContentMode = Field(description="Content mode used")
    strict_grounded: bool = Field(default=True)
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    transcript_hash: str = Field(description="Hash for cache invalidation")
    chapters: List[ChapterEvidence] = Field(default_factory=list)
    global_context: Optional[GlobalContext] = Field(default=None)
