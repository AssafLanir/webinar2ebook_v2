"""Style config models for Webinar2Ebook Tab 3 (AI Draft).

Canonical schema lives in backend (Pydantic). Frontend should mirror via OpenAPI
(preferred) or TS types.

Notes:
- Pydantic v2.
- Extra fields are forbidden to prevent drift and accidental prompt injection.
"""

from __future__ import annotations

from enum import Enum
from typing import List, Literal, Optional

from pydantic import BaseModel, Field, ConfigDict, model_validator


class ContentMode(str, Enum):
    """Content type that determines structure and constraints (Spec 009)."""
    interview = "interview"  # Narrative, speaker insights, quotes
    essay = "essay"          # Argument/thesis structure
    tutorial = "tutorial"    # Step-by-step, action items allowed


class TargetAudience(str, Enum):
    beginners = "beginners"
    intermediate = "intermediate"
    advanced = "advanced"
    mixed = "mixed"


class ReaderRole(str, Enum):
    founder = "founder"
    marketer = "marketer"
    sales = "sales"
    product = "product"
    engineer = "engineer"
    hr = "hr"
    finance = "finance"
    educator = "educator"
    general = "general"


class PrimaryGoal(str, Enum):
    teach = "teach"
    persuade = "persuade"
    inform = "inform"
    enable_action = "enable_action"
    thought_leadership = "thought_leadership"


class ReaderTakeawayStyle(str, Enum):
    steps = "steps"
    principles = "principles"
    templates = "templates"
    case_studies = "case_studies"
    q_and_a = "q_and_a"


class Tone(str, Enum):
    friendly = "friendly"
    professional = "professional"
    authoritative = "authoritative"
    conversational = "conversational"
    academic = "academic"


class Formality(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"


class BrandVoice(str, Enum):
    neutral = "neutral"
    bold = "bold"
    playful = "playful"
    premium = "premium"
    minimalist = "minimalist"


class Perspective(str, Enum):
    we = "we"
    you = "you"
    third_person = "third_person"


class ReadingLevel(str, Enum):
    simple = "simple"
    standard = "standard"
    technical = "technical"


class BookFormat(str, Enum):
    playbook = "playbook"
    handbook = "handbook"
    tutorial = "tutorial"
    guide = "guide"
    ebook_marketing = "ebook_marketing"
    executive_brief = "executive_brief"
    course_notes = "course_notes"


class ChapterLengthTarget(str, Enum):
    short = "short"
    medium = "medium"
    long = "long"


class TotalLengthPreset(str, Enum):
    """Controls overall draft length target."""
    brief = "brief"  # ~2,000 words
    standard = "standard"  # ~5,000 words
    comprehensive = "comprehensive"  # ~10,000 words
    custom = "custom"  # user-specified total_target_words


# Validation constants for custom word count
MIN_CUSTOM_WORDS = 800
MAX_CUSTOM_WORDS = 50000


class DetailLevel(str, Enum):
    """Controls depth/density of content."""
    concise = "concise"  # fewer examples, tighter bullets, avoid tangents
    balanced = "balanced"  # normal explanatory tone
    detailed = "detailed"  # more examples, step-by-step, frameworks/checklists


class FaithfulnessLevel(str, Enum):
    strict = "strict"
    balanced = "balanced"
    creative = "creative"


class AllowedExtrapolation(str, Enum):
    none = "none"
    light = "light"
    moderate = "moderate"


class SourcePolicy(str, Enum):
    transcript_only = "transcript_only"
    transcript_plus_provided_resources = "transcript_plus_provided_resources"


class CitationStyle(str, Enum):
    none = "none"
    inline_links = "inline_links"
    footnotes_light = "footnotes_light"


class VisualDensity(str, Enum):
    none = "none"
    light = "light"
    medium = "medium"
    heavy = "heavy"


class VisualType(str, Enum):
    screenshot = "screenshot"
    diagram = "diagram"
    chart = "chart"
    table = "table"
    icon = "icon"
    photo = "photo"
    other = "other"


class VisualSourcePolicy(str, Enum):
    client_assets_only = "client_assets_only"
    allow_new_suggestions = "allow_new_suggestions"


class CaptionStyle(str, Enum):
    short = "short"
    explanatory = "explanatory"
    instructional = "instructional"


class DiagramStyle(str, Enum):
    simple = "simple"
    detailed = "detailed"
    brand_like = "brand_like"


class ResolveRepetitions(str, Enum):
    keep = "keep"
    reduce = "reduce"
    aggressive_reduce = "aggressive_reduce"


class HandleQAndA(str, Enum):
    append_as_faq = "append_as_faq"
    weave_into_chapters = "weave_into_chapters"
    omit = "omit"


class IncludeSpeakerQuotes(str, Enum):
    none = "none"
    sparingly = "sparingly"
    often = "often"


class HeadingStyle(str, Enum):
    atx = "atx"


class CalloutBlocks(str, Enum):
    none = "none"
    tip_warning_note = "tip_warning_note"


class TablePreference(str, Enum):
    markdown_tables = "markdown_tables"
    bullet_lists = "bullet_lists"


class StyleConfig(BaseModel):
    """User-selected options that shape the generated ebook draft."""

    model_config = ConfigDict(extra="forbid")

    # Audience and intent
    target_audience: TargetAudience = Field(default=TargetAudience.mixed)
    reader_role: ReaderRole = Field(default=ReaderRole.general)
    primary_goal: PrimaryGoal = Field(default=PrimaryGoal.inform)
    reader_takeaway_style: ReaderTakeawayStyle = Field(default=ReaderTakeawayStyle.principles)

    # Voice and tone
    tone: Tone = Field(default=Tone.professional)
    formality: Formality = Field(default=Formality.medium)
    brand_voice: BrandVoice = Field(default=BrandVoice.neutral)
    perspective: Perspective = Field(default=Perspective.you)
    reading_level: ReadingLevel = Field(default=ReadingLevel.standard)

    # Structure and pacing
    book_format: BookFormat = Field(default=BookFormat.guide)
    chapter_count_target: int = Field(default=8, ge=3, le=20)  # Deprecated: outline determines chapters
    chapter_length_target: ChapterLengthTarget = Field(default=ChapterLengthTarget.medium)  # Deprecated

    # Length and detail controls (new)
    total_length_preset: TotalLengthPreset = Field(default=TotalLengthPreset.standard)
    total_target_words: Optional[int] = Field(default=None, ge=MIN_CUSTOM_WORDS, le=MAX_CUSTOM_WORDS)
    detail_level: DetailLevel = Field(default=DetailLevel.balanced)

    include_summary_per_chapter: bool = Field(default=True)
    include_key_takeaways: bool = Field(default=True)
    include_action_steps: bool = Field(default=True)
    include_checklists: bool = Field(default=False)
    include_templates: bool = Field(default=False)
    include_examples: bool = Field(default=True)

    # Content mode and grounding (Spec 009)
    content_mode: ContentMode = Field(
        default=ContentMode.interview,
        description="Type of source content - affects structure and constraints"
    )
    strict_grounded: bool = Field(
        default=True,
        description="When true, only generate content supported by Evidence Map"
    )

    # Accuracy / policy
    faithfulness_level: FaithfulnessLevel = Field(default=FaithfulnessLevel.balanced)
    allowed_extrapolation: AllowedExtrapolation = Field(default=AllowedExtrapolation.light)
    source_policy: SourcePolicy = Field(default=SourcePolicy.transcript_plus_provided_resources)
    citation_style: CitationStyle = Field(default=CitationStyle.inline_links)
    avoid_hallucinations: bool = Field(default=True)

    # Visual strategy (suggestions only; Tab 2 attaches actual assets later)
    visual_density: VisualDensity = Field(default=VisualDensity.light)
    preferred_visual_types: List[VisualType] = Field(default_factory=lambda: [VisualType.diagram, VisualType.table])
    visual_source_policy: VisualSourcePolicy = Field(default=VisualSourcePolicy.client_assets_only)
    caption_style: CaptionStyle = Field(default=CaptionStyle.explanatory)
    diagram_style: DiagramStyle = Field(default=DiagramStyle.simple)

    # Cleanup / editorial
    remove_filler: bool = Field(default=True)
    normalize_punctuation: bool = Field(default=True)
    resolve_repetitions: ResolveRepetitions = Field(default=ResolveRepetitions.reduce)
    handle_q_and_a: HandleQAndA = Field(default=HandleQAndA.append_as_faq)
    include_speaker_quotes: IncludeSpeakerQuotes = Field(default=IncludeSpeakerQuotes.sparingly)

    # Output format
    output_format: Literal["markdown"] = Field(default="markdown")
    heading_style: HeadingStyle = Field(default=HeadingStyle.atx)
    callout_blocks: CalloutBlocks = Field(default=CalloutBlocks.tip_warning_note)
    table_preference: TablePreference = Field(default=TablePreference.markdown_tables)

    @model_validator(mode="after")
    def validate_custom_word_count(self) -> "StyleConfig":
        """Validate total_target_words is set when preset is custom."""
        if self.total_length_preset == TotalLengthPreset.custom:
            if self.total_target_words is None:
                raise ValueError(
                    "total_target_words is required when total_length_preset is 'custom'"
                )
        return self


STYLE_CONFIG_VERSION = 1


class StyleConfigEnvelope(BaseModel):
    """Versioned wrapper for persistence/migrations."""

    model_config = ConfigDict(extra="forbid")

    version: int = Field(default=STYLE_CONFIG_VERSION, ge=1)
    preset_id: str = Field(default="default_webinar_ebook_v1")
    style: StyleConfig = Field(default_factory=StyleConfig)


def style_config_json_schema() -> dict:
    """Return JSON Schema for StyleConfig (useful for structured outputs)."""
    return StyleConfig.model_json_schema()


# Word count targets for each preset
TOTAL_LENGTH_WORD_TARGETS = {
    TotalLengthPreset.brief: 2000,
    TotalLengthPreset.standard: 5000,
    TotalLengthPreset.comprehensive: 10000,
}

# Clamp bounds for words per chapter
MIN_WORDS_PER_CHAPTER = 250
MAX_WORDS_PER_CHAPTER = 2500


def compute_words_per_chapter(
    total_length_preset: TotalLengthPreset,
    chapter_count: int,
    custom_total_words: Optional[int] = None,
) -> int:
    """Compute target words per chapter from preset and chapter count.

    Args:
        total_length_preset: The selected length preset (brief/standard/comprehensive/custom)
        chapter_count: Number of chapters (from outline)
        custom_total_words: Custom word count (required when preset is 'custom')

    Returns:
        Clamped words-per-chapter target (250-2500)
    """
    if chapter_count <= 0:
        return MIN_WORDS_PER_CHAPTER

    # Determine total words based on preset
    if total_length_preset == TotalLengthPreset.custom:
        if custom_total_words is None:
            total_words = 5000  # Fallback to standard if custom but no value
        else:
            total_words = custom_total_words
    else:
        total_words = TOTAL_LENGTH_WORD_TARGETS.get(total_length_preset, 5000)

    words_per_chapter = round(total_words / chapter_count)

    # Clamp to sensible bounds
    return max(MIN_WORDS_PER_CHAPTER, min(MAX_WORDS_PER_CHAPTER, words_per_chapter))
