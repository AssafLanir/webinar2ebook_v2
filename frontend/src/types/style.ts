// Tab 3 Style Config types (mirrors backend/src/models/style_config.py).
// Prefer generating types from OpenAPI later to avoid drift.

// Content mode for Evidence-Grounded Drafting (Spec 009)
export type ContentMode = "interview" | "essay" | "tutorial";

export type TargetAudience = "beginners" | "intermediate" | "advanced" | "mixed";
export type ReaderRole =
  | "founder"
  | "marketer"
  | "sales"
  | "product"
  | "engineer"
  | "hr"
  | "finance"
  | "educator"
  | "general";

export type PrimaryGoal = "teach" | "persuade" | "inform" | "enable_action" | "thought_leadership";
export type ReaderTakeawayStyle = "steps" | "principles" | "templates" | "case_studies" | "q_and_a";

export type Tone = "friendly" | "professional" | "authoritative" | "conversational" | "academic";
export type Formality = "low" | "medium" | "high";
export type BrandVoice = "neutral" | "bold" | "playful" | "premium" | "minimalist";
export type Perspective = "we" | "you" | "third_person";
export type ReadingLevel = "simple" | "standard" | "technical";

export type BookFormat =
  | "playbook"
  | "handbook"
  | "tutorial"
  | "guide"
  | "ebook_marketing"
  | "executive_brief"
  | "course_notes"
  | "interview_qa";

export type ChapterLengthTarget = "short" | "medium" | "long";

// Length and detail controls (new)
export type TotalLengthPreset = "brief" | "standard" | "comprehensive" | "custom";
export type DetailLevel = "concise" | "balanced" | "detailed";

// Word count targets for each preset (custom excluded - uses total_target_words)
export const TOTAL_LENGTH_WORD_TARGETS: Record<Exclude<TotalLengthPreset, "custom">, number> = {
  brief: 2000,
  standard: 5000,
  comprehensive: 10000,
};

// Validation constants for custom word count
export const MIN_CUSTOM_WORDS = 800;
export const MAX_CUSTOM_WORDS = 50000;

// Helper to compute words per chapter
export function computeWordsPerChapter(
  totalLengthPreset: TotalLengthPreset,
  chapterCount: number,
  customTotalWords?: number | null
): number {
  if (chapterCount <= 0) return 250;

  let totalWords: number;
  if (totalLengthPreset === "custom") {
    totalWords = customTotalWords ?? 5000; // Fallback to standard if custom but no value
  } else {
    totalWords = TOTAL_LENGTH_WORD_TARGETS[totalLengthPreset] ?? 5000;
  }

  const wordsPerChapter = Math.round(totalWords / chapterCount);
  // Clamp to [250, 2500]
  return Math.max(250, Math.min(2500, wordsPerChapter));
}

export type FaithfulnessLevel = "strict" | "balanced" | "creative";
export type AllowedExtrapolation = "none" | "light" | "moderate";
export type SourcePolicy = "transcript_only" | "transcript_plus_provided_resources";
export type CitationStyle = "none" | "inline_links" | "footnotes_light";

export type VisualDensity = "none" | "light" | "medium" | "heavy";
export type VisualType = "screenshot" | "diagram" | "chart" | "table" | "icon" | "photo" | "other";
export type VisualSourcePolicy = "client_assets_only" | "allow_new_suggestions";
export type CaptionStyle = "short" | "explanatory" | "instructional";
export type DiagramStyle = "simple" | "detailed" | "brand_like";

export type ResolveRepetitions = "keep" | "reduce" | "aggressive_reduce";
export type HandleQAndA = "append_as_faq" | "weave_into_chapters" | "omit";
export type IncludeSpeakerQuotes = "none" | "sparingly" | "often";

export type HeadingStyle = "atx";
export type CalloutBlocks = "none" | "tip_warning_note";
export type TablePreference = "markdown_tables" | "bullet_lists";

export interface StyleConfig {
  target_audience?: TargetAudience;
  reader_role?: ReaderRole;
  primary_goal?: PrimaryGoal;
  reader_takeaway_style?: ReaderTakeawayStyle;

  tone: Tone;
  formality?: Formality;
  brand_voice?: BrandVoice;
  perspective?: Perspective;
  reading_level?: ReadingLevel;

  book_format: BookFormat;
  chapter_count_target?: number; // 3..20 (deprecated: outline determines chapters)
  chapter_length_target?: ChapterLengthTarget; // deprecated

  // Length and detail controls (new)
  total_length_preset?: TotalLengthPreset;
  total_target_words?: number | null; // Required when total_length_preset is 'custom'
  detail_level?: DetailLevel;

  include_summary_per_chapter?: boolean;
  include_key_takeaways?: boolean;
  include_action_steps?: boolean;
  include_checklists?: boolean;
  include_templates?: boolean;
  include_examples?: boolean;

  // Content mode and grounding (Spec 009)
  content_mode?: ContentMode;
  strict_grounded?: boolean;

  faithfulness_level?: FaithfulnessLevel;
  allowed_extrapolation?: AllowedExtrapolation;
  source_policy?: SourcePolicy;
  citation_style?: CitationStyle;
  avoid_hallucinations?: boolean;

  visual_density?: VisualDensity;
  preferred_visual_types?: VisualType[];
  visual_source_policy?: VisualSourcePolicy;
  caption_style?: CaptionStyle;
  diagram_style?: DiagramStyle;

  remove_filler?: boolean;
  normalize_punctuation?: boolean;
  resolve_repetitions?: ResolveRepetitions;
  handle_q_and_a?: HandleQAndA;
  include_speaker_quotes?: IncludeSpeakerQuotes;

  output_format?: "markdown";
  heading_style?: HeadingStyle;
  callout_blocks?: CalloutBlocks;
  table_preference?: TablePreference;
}

export interface StyleConfigEnvelope {
  version: number; // currently 1
  preset_id: string;
  style: StyleConfig;
}
