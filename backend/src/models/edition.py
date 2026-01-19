"""Edition-related enums and models for the Editions feature.

These enums define the different edition types, fidelity levels,
and coverage strengths used throughout the system.

Models include:
- SegmentRef: Reference to a transcript segment with canonical_hash for offset drift protection
- Theme: A theme/chapter for Ideas Edition
- SpeakerRole: Role of speaker in transcript (host, guest, caller, clip, unclear)
- SpeakerRef: Reference to a speaker with typed role for whitelist-based quote generation
- TranscriptPair: Both transcript forms needed for whitelist building
- WhitelistQuote: A validated quote that can be used in generation
"""

from enum import Enum
from typing import Annotated, Literal

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


class CoverageLevel(str, Enum):
    """Coverage strength for quote availability.

    STRONG: >= 5 usable quotes, >= 50 words/claim
    MEDIUM: >= 3 usable quotes, >= 30 words/claim
    WEAK: Below MEDIUM thresholds
    """

    STRONG = "strong"
    MEDIUM = "medium"
    WEAK = "weak"


class ChapterCoverage(BaseModel):
    """Coverage metrics for a chapter."""

    model_config = ConfigDict(extra="forbid")

    chapter_index: int = Field(ge=0)
    level: CoverageLevel
    usable_quotes: int = Field(ge=0)
    quote_words_per_claim: float = Field(ge=0)
    quotes_per_claim: float = Field(ge=0)
    target_words: int = Field(ge=0)
    generation_mode: Literal["normal", "thin", "excerpt_only"] = Field(
        description="Generation mode based on coverage level"
    )


class SpeakerRole(str, Enum):
    """Role of speaker in transcript.

    HOST: The host/interviewer of the podcast/webinar
    GUEST: A guest being interviewed or featured
    CALLER: A caller or audience member
    CLIP: Audio/video clip from another source
    UNCLEAR: Speaker role cannot be determined
    """

    HOST = "host"
    GUEST = "guest"
    CALLER = "caller"
    CLIP = "clip"
    UNCLEAR = "unclear"


class SpeakerRef(BaseModel):
    """Reference to a speaker with typed role.

    Used for whitelist-based quote generation to filter quotes by speaker role.
    """

    model_config = ConfigDict(extra="forbid")

    speaker_id: str = Field(description="Canonical stable ID (e.g., 'david_deutsch')")
    speaker_name: str = Field(description="Display name (e.g., 'David Deutsch')")
    speaker_role: SpeakerRole = Field(description="Role for filtering")


class TranscriptPair(BaseModel):
    """Both transcript forms needed for whitelist building."""

    model_config = ConfigDict(extra="forbid")

    raw: str = Field(description="Original transcript (for quote_text extraction)")
    canonical: str = Field(description="Normalized (for matching)")


class WhitelistQuote(BaseModel):
    """A validated quote that can be used in generation."""

    model_config = ConfigDict(extra="forbid")

    quote_id: str = Field(
        min_length=16,
        max_length=16,
        pattern=r"^[a-f0-9]{16}$",
        description="Stable ID: sha256(speaker_id|quote_canonical)[:16]"
    )
    quote_text: str = Field(description="EXACT from raw transcript (for output)")
    quote_canonical: str = Field(description="Casefolded/normalized (for matching only)")
    speaker: SpeakerRef
    source_evidence_ids: list[str] = Field(default_factory=list)
    chapter_indices: list[int] = Field(default_factory=list)
    match_spans: list[tuple[int, int]] = Field(default_factory=list)


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


def get_recommended_edition(webinar_type: str) -> Edition:
    """Get recommended edition based on webinar type.

    - Presentations and tutorials → Ideas Edition (thematic chapters)
    - Interviews → Q&A Edition (speaker-labeled dialogue)

    Args:
        webinar_type: The webinar type string value

    Returns:
        The recommended Edition enum value
    """
    if webinar_type == "interview":
        return Edition.QA
    # standard_presentation, training_tutorial, or any other type
    return Edition.IDEAS
