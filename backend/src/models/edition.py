"""Edition-related enums and models for the Editions feature.

These enums define the different edition types, fidelity levels,
and coverage strengths used throughout the system.

Models include:
- SegmentRef: Reference to a transcript segment with canonical_hash for offset drift protection
- Theme: A theme/chapter for Ideas Edition
"""

from enum import Enum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field


class Edition(str, Enum):
    """Type of edition to generate.

    QA: Question-and-answer format preserving interview structure
    IDEAS: Key ideas extraction format
    """

    QA = "qa"
    IDEAS = "ideas"


class Fidelity(str, Enum):
    """Fidelity level for content generation.

    FAITHFUL: Maintains meaning while allowing minor rephrasing
    VERBATIM: Exact word-for-word preservation
    """

    FAITHFUL = "faithful"
    VERBATIM = "verbatim"


class Coverage(str, Enum):
    """Coverage strength indicating how well content is supported.

    STRONG: Content is well-supported by evidence
    MEDIUM: Content has moderate support
    WEAK: Content has minimal support
    """

    STRONG = "strong"
    MEDIUM = "medium"
    WEAK = "weak"


class SegmentRef(BaseModel):
    """Reference to a transcript segment.

    CRITICAL: canonical_hash stores the SHA256 hash of the canonical transcript
    these offsets reference. This prevents offset drift if the transcript changes.
    """

    model_config = ConfigDict(extra="forbid")

    start_offset: Annotated[int, Field(ge=0, description="Start character offset, must be >= 0")]
    end_offset: Annotated[int, Field(ge=0, description="End character offset, must be >= 0")]
    token_count: Annotated[int, Field(ge=0, description="Actual token count, NOT from preview")]
    text_preview: str = Field(description="First ~100 chars for display only")
    canonical_hash: str = Field(
        description="SHA256 hash of canonical transcript (REQUIRED for offset validity)"
    )


class Theme(BaseModel):
    """A theme/chapter for Ideas Edition."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(description="Unique theme identifier")
    title: str = Field(description="Theme title")
    one_liner: str = Field(description="Brief description of the theme")
    keywords: list[str] = Field(description="Keywords associated with this theme")
    coverage: Coverage = Field(description="Coverage strength of this theme")
    supporting_segments: list[SegmentRef] = Field(
        description="Transcript segments supporting this theme"
    )
    include_in_generation: bool = Field(
        default=True,
        description="Whether to include this theme in generation"
    )
