import type { StyleConfig, StyleConfigEnvelope } from './style'
import type { VisualPlan } from './visuals'
import type { Edition, Fidelity, Theme } from './edition'

// Webinar Type - aligned with backend
export type WebinarType = 'standard_presentation' | 'training_tutorial' | 'interview'

export const WEBINAR_TYPE_LABELS: Record<WebinarType, string> = {
  standard_presentation: 'Standard Presentation',
  training_tutorial: 'Training / Tutorial',
  interview: 'Interview',
}

// Style Config - re-export from dedicated file
export type { StyleConfig, StyleConfigEnvelope } from './style'

// Visual Plan - re-export from dedicated file
export type { VisualPlan, VisualOpportunity, VisualAsset } from './visuals'

// Edition types - re-export from dedicated file
export type { Edition, Fidelity, Theme, Coverage, SegmentRef, ThemeJob, ThemeJobStatus } from './edition'
export {
  EDITION_LABELS,
  EDITION_DESCRIPTIONS,
  FIDELITY_LABELS,
  FIDELITY_DESCRIPTIONS,
  COVERAGE_LABELS,
  COVERAGE_COLORS,
  DEFAULT_EDITION,
  DEFAULT_FIDELITY,
} from './edition'

// Legacy style config for backward compatibility with existing data
export interface LegacyStyleConfig {
  audience?: string
  tone?: string
  depth?: string
  targetPages?: number
}

// Outline Item - aligned with backend
export interface OutlineItem {
  id: string
  title: string
  level: number
  notes?: string
  order: number
}

// Resource Type - aligned with backend
export type ResourceType = 'url_or_note' | 'file'

// Resource - aligned with backend (supports both URL/note and file resources)
export interface Resource {
  id: string
  label: string
  order: number
  resourceType: ResourceType
  // URL/Note fields
  urlOrNote: string
  // File fields (optional, only present for file resources)
  fileId?: string
  fileName?: string
  fileSize?: number
  mimeType?: string
  storagePath?: string
}

// Visual - aligned with backend
export interface Visual {
  id: string
  title: string
  description: string
  selected: boolean
  isCustom?: boolean
  order?: number
}

// Project Summary (for list view) - new type for backend alignment
export interface ProjectSummary {
  id: string
  name: string
  webinarType: WebinarType
  updatedAt: string
}

// Project - aligned with backend (uses 'id' and 'name' instead of 'projectId' and 'title')
export interface Project {
  // Identity & Metadata
  id: string
  name: string
  webinarType: WebinarType
  createdAt: string
  updatedAt: string

  // Edition Settings (Editions feature)
  edition: Edition
  fidelity: Fidelity
  themes: Theme[]
  canonical_transcript: string | null
  canonical_transcript_hash: string | null

  // Stage 1: Transcript, Outline & Resources
  transcriptText: string
  outlineItems: OutlineItem[]
  resources: Resource[]

  // Stage 2: Visuals
  visuals: Visual[]

  // Stage 3: Draft
  draftText: string
  styleConfig: StyleConfigEnvelope | LegacyStyleConfig | null
  visualPlan: VisualPlan | null

  // Stage 4: Final & Export
  finalTitle: string
  finalSubtitle: string
  creditsText: string
}

// Tab Navigation
export type TabIndex = 1 | 2 | 3 | 4

export const TAB_LABELS: Record<TabIndex, string> = {
  1: 'Transcript, Outline & Resources',
  2: 'Visuals',
  3: 'Draft',
  4: 'Final & Export',
}

// Context State - updated to handle project list view
export type AppView = 'list' | 'workspace'

// AI Action Types (for state tracking)
export type AIActionType = 'clean-transcript' | 'suggest-outline' | 'suggest-resources'

export interface AIActionState {
  /** Currently running AI action, or null if idle */
  inProgress: AIActionType | null
  /** Error message from last failed action, or null */
  error: string | null
}

// AI Preview Data Types
export type AIPreviewData =
  | { type: 'clean-transcript'; cleanedTranscript: string }
  | { type: 'suggest-outline'; items: Array<{ title: string; level: number; notes?: string }>; selected: Set<number> }
  | { type: 'suggest-resources'; resources: Array<{ label: string; url_or_note: string }>; selected: Set<number> }

export interface AIPreviewState {
  /** Whether the preview modal is open */
  isOpen: boolean
  /** Preview data, or null if no preview */
  preview: AIPreviewData | null
}

export interface ProjectState {
  view: AppView
  projectList: ProjectSummary[]
  project: Project | null
  activeTab: TabIndex
  isExportModalOpen: boolean
  isLoading: boolean
  isSaving: boolean
  saveError: string | null
  error: string | null
  // AI state
  aiAction: AIActionState
  aiPreview: AIPreviewState
}

export const INITIAL_STATE: ProjectState = {
  view: 'list',
  projectList: [],
  project: null,
  activeTab: 1,
  isExportModalOpen: false,
  isLoading: false,
  isSaving: false,
  saveError: null,
  error: null,
  // AI initial state
  aiAction: {
    inProgress: null,
    error: null,
  },
  aiPreview: {
    isOpen: false,
    preview: null,
  },
}

// Default StyleConfigEnvelope for new projects
export const DEFAULT_STYLE_CONFIG: StyleConfigEnvelope = {
  version: 1,
  preset_id: 'default_webinar_ebook_v1',
  style: {
    target_audience: 'mixed',
    reader_role: 'general',
    primary_goal: 'enable_action',
    reader_takeaway_style: 'principles',
    tone: 'professional',
    formality: 'medium',
    brand_voice: 'neutral',
    perspective: 'you',
    reading_level: 'standard',
    book_format: 'guide',
    chapter_count_target: 8,
    chapter_length_target: 'medium',
    include_summary_per_chapter: true,
    include_key_takeaways: true,
    include_action_steps: true,
    include_examples: true,
    faithfulness_level: 'balanced',
    allowed_extrapolation: 'light',
    source_policy: 'transcript_plus_provided_resources',
    citation_style: 'inline_links',
    avoid_hallucinations: true,
    visual_density: 'light',
    preferred_visual_types: ['diagram', 'table', 'screenshot'],
    visual_source_policy: 'client_assets_only',
    caption_style: 'explanatory',
    diagram_style: 'simple',
    resolve_repetitions: 'reduce',
    handle_q_and_a: 'append_as_faq',
    include_speaker_quotes: 'sparingly',
    output_format: 'markdown',
  },
}

// Action Types - expanded for API integration
export type ProjectAction =
  // View navigation
  | { type: 'SET_VIEW'; payload: AppView }
  | { type: 'SET_LOADING'; payload: boolean }
  | { type: 'SET_ERROR'; payload: string | null }
  | { type: 'SET_SAVING'; payload: boolean }
  | { type: 'SET_SAVE_ERROR'; payload: string | null }

  // Project list
  | { type: 'SET_PROJECT_LIST'; payload: ProjectSummary[] }

  // Project lifecycle
  | { type: 'SET_PROJECT'; payload: Project }
  | { type: 'UPDATE_PROJECT_DATA'; payload: Project }  // Updates project without changing tab
  | { type: 'CREATE_PROJECT'; payload: { name: string; webinarType: WebinarType } }
  | { type: 'CLEAR_PROJECT' }

  // Tab navigation
  | { type: 'SET_ACTIVE_TAB'; payload: TabIndex }

  // Tab 1: Transcript, Outline & Resources
  | { type: 'UPDATE_TRANSCRIPT'; payload: string }
  | { type: 'ADD_OUTLINE_ITEM'; payload: { title: string; level?: number } }
  | { type: 'UPDATE_OUTLINE_ITEM'; payload: { id: string; updates: Partial<OutlineItem> } }
  | { type: 'REMOVE_OUTLINE_ITEM'; payload: string }
  | { type: 'REORDER_OUTLINE_ITEMS'; payload: string[] }
  | { type: 'ADD_RESOURCE'; payload: { label: string; urlOrNote?: string } }
  | { type: 'ADD_FILE_RESOURCE'; payload: Resource }
  | { type: 'UPDATE_RESOURCE'; payload: { id: string; updates: Partial<Resource> } }
  | { type: 'REMOVE_RESOURCE'; payload: string }
  | { type: 'FILL_SAMPLE_DATA' }

  // Tab 2: Visuals (Legacy)
  | { type: 'TOGGLE_VISUAL_SELECTION'; payload: string }
  | { type: 'ADD_CUSTOM_VISUAL'; payload: { title: string; description: string } }

  // Tab 2: Visual Assets (Spec 005)
  | { type: 'ADD_VISUAL_ASSET'; payload: import('./visuals').VisualAsset }
  | { type: 'ADD_VISUAL_ASSETS'; payload: import('./visuals').VisualAsset[] }
  | { type: 'REMOVE_VISUAL_ASSET'; payload: string }  // assetId
  | { type: 'UPDATE_VISUAL_ASSET_METADATA'; payload: { assetId: string; updates: { caption?: string; alt_text?: string } } }

  // Tab 2: Visual Assignments (Spec 005 - US2)
  | { type: 'SET_VISUAL_ASSIGNMENT'; payload: { opportunityId: string; assetId: string } }
  | { type: 'SKIP_VISUAL_OPPORTUNITY'; payload: string }  // opportunityId
  | { type: 'REMOVE_VISUAL_ASSIGNMENT'; payload: string }  // opportunityId

  // Tab 3: Draft
  | { type: 'SET_STYLE_PRESET'; payload: string }
  | { type: 'SET_STYLE_CONFIG_ENVELOPE'; payload: StyleConfigEnvelope }
  | { type: 'UPDATE_STYLE_CONFIG'; payload: Partial<StyleConfig> }
  | { type: 'UPDATE_DRAFT'; payload: string }
  | { type: 'SET_VISUAL_PLAN'; payload: VisualPlan | null }
  | { type: 'GENERATE_SAMPLE_DRAFT' }

  // Tab 4: Final & Export
  | { type: 'UPDATE_FINAL_TITLE'; payload: string }
  | { type: 'UPDATE_FINAL_SUBTITLE'; payload: string }
  | { type: 'UPDATE_CREDITS'; payload: string }
  | { type: 'TOGGLE_EXPORT_MODAL' }

  // AI Actions (T021)
  | { type: 'START_AI_ACTION'; payload: AIActionType }
  | { type: 'AI_ACTION_SUCCESS'; payload: AIPreviewData }
  | { type: 'AI_ACTION_ERROR'; payload: string }

  // AI Preview Actions (T022)
  | { type: 'APPLY_AI_PREVIEW' }
  | { type: 'DISCARD_AI_PREVIEW' }
  | { type: 'TOGGLE_AI_PREVIEW_SELECTION'; payload: number }
