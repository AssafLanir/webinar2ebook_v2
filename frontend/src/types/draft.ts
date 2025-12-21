/**
 * Draft Generation Types
 *
 * Types for AI draft generation: async job pattern, progress tracking, and results.
 * Matches backend models from backend/src/models/api_responses.py
 */

import type { StyleConfigEnvelope } from './style'
import type { VisualPlan } from './visuals'

// ============================================================================
// Job Status
// ============================================================================

export type JobStatus = 'queued' | 'planning' | 'generating' | 'completed' | 'cancelled' | 'failed'

// ============================================================================
// Progress and Stats
// ============================================================================

export interface GenerationProgress {
  current_chapter: number
  total_chapters: number
  current_chapter_title?: string
  chapters_completed: number
  estimated_remaining_seconds?: number
}

export interface TokenUsage {
  prompt_tokens: number
  completion_tokens: number
  total_tokens: number
}

export interface GenerationStats {
  chapters_generated: number
  total_words: number
  generation_time_ms: number
  tokens_used: TokenUsage
}

// ============================================================================
// DraftPlan Types (from backend models)
// ============================================================================

export type TranscriptRelevance = 'primary' | 'supporting' | 'reference'

export interface TranscriptSegment {
  start_char: number
  end_char: number
  relevance: TranscriptRelevance
}

export interface ChapterPlan {
  chapter_number: number
  title: string
  outline_item_id: string
  goals: string[]
  key_points: string[]
  transcript_segments: TranscriptSegment[]
  estimated_words: number
}

export interface GenerationMetadata {
  estimated_total_words: number
  estimated_generation_time_seconds: number
  transcript_utilization: number
}

export interface DraftPlan {
  version: number
  book_title: string
  chapters: ChapterPlan[]
  visual_plan: VisualPlan
  generation_metadata: GenerationMetadata
}

// ============================================================================
// Request Types
// ============================================================================

export interface OutlineItem {
  id: string
  title: string
  level: number
  notes?: string
}

export interface Resource {
  label: string
  url_or_note: string
}

export interface DraftGenerateRequest {
  transcript: string
  outline: OutlineItem[]
  resources?: Resource[]
  style_config: StyleConfigEnvelope | Record<string, unknown>
}

export interface DraftRegenerateRequest {
  section_outline_item_id: string
  draft_plan: DraftPlan
  existing_draft: string
  style_config: StyleConfigEnvelope | Record<string, unknown>
}

// ============================================================================
// Response Data Types
// ============================================================================

export interface DraftGenerateData {
  job_id: string
  status: JobStatus
  progress?: GenerationProgress
  draft_markdown?: string
  draft_plan?: DraftPlan
  visual_plan?: VisualPlan
  generation_stats?: GenerationStats
}

export interface DraftStatusData {
  job_id: string
  status: JobStatus
  progress?: GenerationProgress
  draft_markdown?: string
  draft_plan?: DraftPlan
  visual_plan?: VisualPlan
  generation_stats?: GenerationStats
  partial_draft_markdown?: string
  chapters_available?: number
  error_code?: string
  error_message?: string
}

export interface DraftCancelData {
  job_id: string
  status: JobStatus
  cancelled: boolean
  message: string
  partial_draft_markdown?: string
  chapters_available?: number
}

export interface DraftRegenerateData {
  section_markdown: string
  section_start_line: number
  section_end_line: number
  generation_stats?: GenerationStats
}

// ============================================================================
// UI State Types
// ============================================================================

export type DraftGenerationPhase = 'idle' | 'starting' | 'planning' | 'generating' | 'completed' | 'cancelled' | 'failed'

export interface DraftGenerationState {
  /** Current phase of generation */
  phase: DraftGenerationPhase
  /** Job ID for active generation */
  jobId: string | null
  /** Progress info during generation */
  progress: GenerationProgress | null
  /** Error message if failed */
  error: string | null
  /** Generated draft markdown */
  draftMarkdown: string | null
  /** Generation plan */
  draftPlan: DraftPlan | null
  /** Visual opportunities */
  visualPlan: VisualPlan | null
  /** Statistics after completion */
  stats: GenerationStats | null
}

export const initialDraftGenerationState: DraftGenerationState = {
  phase: 'idle',
  jobId: null,
  progress: null,
  error: null,
  draftMarkdown: null,
  draftPlan: null,
  visualPlan: null,
  stats: null,
}

// ============================================================================
// Preview Modal State
// ============================================================================

export interface DraftPreviewState {
  /** Whether the preview modal is open */
  isOpen: boolean
  /** Draft markdown to preview */
  markdown: string | null
  /** Word count */
  wordCount: number
  /** Chapter count */
  chapterCount: number
}

export const initialDraftPreviewState: DraftPreviewState = {
  isOpen: false,
  markdown: null,
  wordCount: 0,
  chapterCount: 0,
}
