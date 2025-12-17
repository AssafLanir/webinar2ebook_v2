/**
 * AI Assist Types
 *
 * Types for AI-assisted features: transcript cleanup, outline suggestion, resource suggestion.
 * These types are ephemeral - preview data is not persisted until applied.
 */

// ============================================================================
// Action Types
// ============================================================================

export type AIActionType = 'clean-transcript' | 'suggest-outline' | 'suggest-resources'

export interface AIActionState {
  /** Currently running AI action, or null if idle */
  inProgress: AIActionType | null
  /** Error message from last failed action, or null */
  error: string | null
}

// ============================================================================
// Response Types (from backend API)
// ============================================================================

export interface CleanTranscriptResponse {
  cleaned_transcript: string
}

export interface SuggestedOutlineItem {
  title: string
  level: number
  notes?: string
}

export interface SuggestOutlineResponse {
  items: SuggestedOutlineItem[]
}

export interface SuggestedResource {
  label: string
  url_or_note: string
}

export interface SuggestResourcesResponse {
  resources: SuggestedResource[]
}

export interface AIErrorResponse {
  error: string
  retry_allowed: boolean
}

// ============================================================================
// Preview State (ephemeral, not in Project)
// ============================================================================

export type AIPreviewData =
  | { type: 'clean-transcript'; data: CleanTranscriptResponse }
  | { type: 'suggest-outline'; data: SuggestOutlineResponse; selected: Set<number> }
  | { type: 'suggest-resources'; data: SuggestResourcesResponse; selected: Set<number> }

export interface AIPreviewState {
  /** Whether the preview modal is open */
  isOpen: boolean
  /** Preview data, or null if no preview */
  preview: AIPreviewData | null
}

// ============================================================================
// Initial State
// ============================================================================

export const initialAIActionState: AIActionState = {
  inProgress: null,
  error: null,
}

export const initialAIPreviewState: AIPreviewState = {
  isOpen: false,
  preview: null,
}
