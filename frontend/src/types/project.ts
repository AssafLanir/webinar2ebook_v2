// Webinar Type - aligned with backend
export type WebinarType = 'standard_presentation' | 'training_tutorial'

export const WEBINAR_TYPE_LABELS: Record<WebinarType, string> = {
  standard_presentation: 'Standard Presentation',
  training_tutorial: 'Training / Tutorial',
}

// Style Config Types
export type AudienceType = 'general' | 'technical' | 'executive' | 'academic'

export type ToneType = 'formal' | 'conversational' | 'instructional' | 'persuasive'

export type DepthLevel = 'overview' | 'moderate' | 'comprehensive'

export interface StyleConfig {
  audience?: string
  tone?: string
  depth?: string
  targetPages?: number
}

export const DEFAULT_STYLE_CONFIG: StyleConfig = {
  audience: 'general',
  tone: 'conversational',
  depth: 'moderate',
  targetPages: 20,
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

  // Stage 1: Transcript, Outline & Resources
  transcriptText: string
  outlineItems: OutlineItem[]
  resources: Resource[]

  // Stage 2: Visuals
  visuals: Visual[]

  // Stage 3: Draft
  draftText: string
  styleConfig: StyleConfig | null

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

  // Tab 2: Visuals
  | { type: 'TOGGLE_VISUAL_SELECTION'; payload: string }
  | { type: 'ADD_CUSTOM_VISUAL'; payload: { title: string; description: string } }

  // Tab 3: Draft
  | { type: 'UPDATE_STYLE_CONFIG'; payload: Partial<StyleConfig> }
  | { type: 'UPDATE_DRAFT'; payload: string }
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
