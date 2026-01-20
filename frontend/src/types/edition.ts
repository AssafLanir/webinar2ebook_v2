/**
 * Edition types for output format selection.
 *
 * Two editions available:
 * - Q&A Edition: Faithful interview format with speaker labels
 * - Ideas Edition: Thematic chapters with synthesized prose
 */

import type { WebinarType } from './project'

/** Output edition type */
export type Edition = 'qa' | 'ideas'

/** Fidelity level for Q&A Edition */
export type Fidelity = 'faithful' | 'verbatim'

/** Theme coverage strength */
export type Coverage = 'strong' | 'medium' | 'weak'

/**
 * Reference to a transcript segment.
 *
 * CRITICAL: canonical_hash stores the SHA256 hash of the canonical transcript
 * these offsets reference. This prevents offset drift if the transcript changes.
 */
export interface SegmentRef {
  start_offset: number
  end_offset: number
  token_count: number
  text_preview: string
  /** SHA256 hash of canonical transcript (REQUIRED for offset validity) */
  canonical_hash: string
}

/** Theme/chapter for Ideas Edition */
export interface Theme {
  id: string
  title: string
  one_liner: string
  keywords: string[]
  coverage: Coverage
  supporting_segments: SegmentRef[]
  include_in_generation: boolean
}

/** Theme proposal job status */
export type ThemeJobStatus = 'queued' | 'processing' | 'completed' | 'failed' | 'cancelled'

/** Theme proposal job */
export interface ThemeJob {
  job_id: string
  project_id: string
  status: ThemeJobStatus
  themes: Theme[]
  error: string | null
}

// UI Labels and Descriptions

export const EDITION_LABELS: Record<Edition, string> = {
  qa: 'Q&A Edition',
  ideas: 'Ideas Edition',
}

export const EDITION_DESCRIPTIONS: Record<Edition, string> = {
  qa: 'Faithful interview format with speaker labels',
  ideas: 'Thematic chapters with synthesized prose',
}

export const FIDELITY_LABELS: Record<Fidelity, string> = {
  faithful: 'Faithful (cleaned)',
  verbatim: 'Verbatim (strict)',
}

export const FIDELITY_DESCRIPTIONS: Record<Fidelity, string> = {
  faithful: 'Cleaned transcript with light editing for readability',
  verbatim: 'Exact word-for-word preservation of speaker words',
}

export const COVERAGE_LABELS: Record<Coverage, string> = {
  strong: 'Strong',
  medium: 'Medium',
  weak: 'Weak',
}

export const COVERAGE_COLORS: Record<Coverage, string> = {
  strong: 'text-green-600 bg-green-100',
  medium: 'text-yellow-600 bg-yellow-100',
  weak: 'text-red-600 bg-red-100',
}

/** Default fidelity for Q&A Edition */
export const DEFAULT_FIDELITY: Fidelity = 'faithful'

/**
 * Get recommended edition based on webinar type.
 *
 * - Presentations and tutorials → Ideas Edition (thematic chapters)
 * - Interviews → Q&A Edition (speaker-labeled dialogue)
 */
export function getRecommendedEdition(webinarType: WebinarType): Edition {
  switch (webinarType) {
    case 'interview':
      return 'qa'
    case 'standard_presentation':
    case 'training_tutorial':
    default:
      return 'ideas'
  }
}

export const EDITION_RECOMMENDATION_REASONS: Record<Edition, string> = {
  qa: 'Best for interview-style content with multiple speakers',
  ideas: 'Best for presentations and tutorials organized by topics',
}
