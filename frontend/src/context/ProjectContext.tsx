import type { ReactNode } from 'react'
import { createContext, useContext, useReducer, useMemo, useEffect, useCallback } from 'react'
import type {
  Project,
  ProjectState,
  ProjectAction,
  TabIndex,
  WebinarType,
  Visual,
  AIPreviewData,
  StyleConfigEnvelope,
} from '../types/project'
import { INITIAL_STATE, DEFAULT_STYLE_CONFIG } from '../types/project'
import { STYLE_PRESETS } from '../constants/stylePresets'
import { generateId } from '../utils/idGenerator'
import {
  SAMPLE_TRANSCRIPT,
  SAMPLE_OUTLINE,
  SAMPLE_RESOURCES,
  SAMPLE_DRAFT_TEXT,
  EXAMPLE_VISUALS,
} from '../data/sampleData'
import { loadState, saveState, clearState } from '../utils/storage'
import {
  createProject as apiCreateProject,
  fetchProject as apiFetchProject,
  updateProject as apiUpdateProject,
  uploadFile as apiUploadFile,
  deleteFile as apiDeleteFile,
  ApiException,
} from '../services/api'
import type { Resource } from '../types/project'

// Context value interface
interface ProjectContextValue {
  state: ProjectState
  dispatch: React.Dispatch<ProjectAction>

  // Convenience methods
  createProject: (name: string, webinarType: WebinarType) => Promise<void>
  openProject: (projectId: string) => Promise<void>
  saveProject: () => Promise<boolean>
  setActiveTab: (tab: TabIndex) => void
  clearProject: () => void
  goToList: () => void
  clearSaveError: () => void

  // File resource methods
  uploadResourceFile: (file: File) => Promise<Resource>
  removeResourceFile: (resourceId: string, fileId: string) => Promise<void>

  // Computed values
  selectedVisuals: Visual[]
  hasProject: boolean
}

// Create context
const ProjectContext = createContext<ProjectContextValue | undefined>(undefined)

// Reducer function
function projectReducer(state: ProjectState, action: ProjectAction): ProjectState {
  switch (action.type) {
    case 'SET_VIEW':
      return { ...state, view: action.payload }

    case 'SET_LOADING':
      return { ...state, isLoading: action.payload }

    case 'SET_ERROR':
      return { ...state, error: action.payload }

    case 'SET_SAVING':
      return { ...state, isSaving: action.payload }

    case 'SET_SAVE_ERROR':
      return { ...state, saveError: action.payload }

    case 'SET_PROJECT':
      return {
        ...state,
        project: action.payload,
        view: 'workspace',
        activeTab: 1,
        isLoading: false,
        error: null,
      }

    case 'CREATE_PROJECT': {
      // This is now used for local fallback only
      const newProject: Project = {
        id: generateId(),
        name: action.payload.name,
        webinarType: action.payload.webinarType,
        createdAt: new Date().toISOString(),
        updatedAt: new Date().toISOString(),
        transcriptText: '',
        outlineItems: [],
        resources: [],
        visuals: EXAMPLE_VISUALS.map(visual => ({
          ...visual,
          id: generateId(),
        })),
        draftText: '',
        styleConfig: { ...DEFAULT_STYLE_CONFIG },
        visualPlan: null,
        finalTitle: '',
        finalSubtitle: '',
        creditsText: '',
      }
      return {
        ...state,
        project: newProject,
        view: 'workspace',
        activeTab: 1,
      }
    }

    case 'CLEAR_PROJECT':
      clearState()
      return { ...INITIAL_STATE }

    case 'SET_ACTIVE_TAB':
      return {
        ...state,
        activeTab: action.payload,
      }

    case 'UPDATE_TRANSCRIPT':
      if (!state.project) return state
      return {
        ...state,
        project: {
          ...state.project,
          transcriptText: action.payload,
        },
      }

    case 'ADD_OUTLINE_ITEM': {
      if (!state.project) return state
      const newItem = {
        id: generateId(),
        title: action.payload.title,
        level: action.payload.level ?? 1,
        order: state.project.outlineItems.length,
      }
      return {
        ...state,
        project: {
          ...state.project,
          outlineItems: [...state.project.outlineItems, newItem],
        },
      }
    }

    case 'UPDATE_OUTLINE_ITEM': {
      if (!state.project) return state
      return {
        ...state,
        project: {
          ...state.project,
          outlineItems: state.project.outlineItems.map(item =>
            item.id === action.payload.id ? { ...item, ...action.payload.updates } : item
          ),
        },
      }
    }

    case 'REMOVE_OUTLINE_ITEM': {
      if (!state.project) return state
      return {
        ...state,
        project: {
          ...state.project,
          outlineItems: state.project.outlineItems
            .filter(item => item.id !== action.payload)
            .map((item, index) => ({ ...item, order: index })),
        },
      }
    }

    case 'REORDER_OUTLINE_ITEMS': {
      if (!state.project) return state
      const orderedIds = action.payload
      const itemMap = new Map(state.project.outlineItems.map(item => [item.id, item]))
      const reorderedItems = orderedIds
        .map((id, index) => {
          const item = itemMap.get(id)
          return item ? { ...item, order: index } : null
        })
        .filter((item): item is NonNullable<typeof item> => item !== null)
      return {
        ...state,
        project: {
          ...state.project,
          outlineItems: reorderedItems,
        },
      }
    }

    case 'ADD_RESOURCE': {
      if (!state.project) return state
      const newResource = {
        id: generateId(),
        label: action.payload.label,
        urlOrNote: action.payload.urlOrNote ?? '',
        order: state.project.resources.length,
        resourceType: 'url_or_note' as const,
      }
      return {
        ...state,
        project: {
          ...state.project,
          resources: [...state.project.resources, newResource],
        },
      }
    }

    case 'ADD_FILE_RESOURCE': {
      if (!state.project) return state
      // The payload is the complete resource from the server upload response
      return {
        ...state,
        project: {
          ...state.project,
          resources: [...state.project.resources, action.payload],
        },
      }
    }

    case 'UPDATE_RESOURCE': {
      if (!state.project) return state
      return {
        ...state,
        project: {
          ...state.project,
          resources: state.project.resources.map(resource =>
            resource.id === action.payload.id
              ? { ...resource, ...action.payload.updates }
              : resource
          ),
        },
      }
    }

    case 'REMOVE_RESOURCE': {
      if (!state.project) return state
      return {
        ...state,
        project: {
          ...state.project,
          resources: state.project.resources
            .filter(resource => resource.id !== action.payload)
            .map((resource, index) => ({ ...resource, order: index })),
        },
      }
    }

    case 'FILL_SAMPLE_DATA': {
      if (!state.project) return state
      return {
        ...state,
        project: {
          ...state.project,
          transcriptText: SAMPLE_TRANSCRIPT,
          outlineItems: SAMPLE_OUTLINE.map((item, index) => ({
            ...item,
            id: generateId(),
            order: index,
          })),
          resources: SAMPLE_RESOURCES.map((resource, index) => ({
            ...resource,
            id: generateId(),
            order: index,
          })),
        },
      }
    }

    case 'TOGGLE_VISUAL_SELECTION': {
      if (!state.project) return state
      return {
        ...state,
        project: {
          ...state.project,
          visuals: state.project.visuals.map(visual =>
            visual.id === action.payload ? { ...visual, selected: !visual.selected } : visual
          ),
        },
      }
    }

    case 'ADD_CUSTOM_VISUAL': {
      if (!state.project) return state
      const newVisual: Visual = {
        id: generateId(),
        title: action.payload.title,
        description: action.payload.description,
        selected: true,
        isCustom: true,
        order: state.project.visuals.length,
      }
      return {
        ...state,
        project: {
          ...state.project,
          visuals: [...state.project.visuals, newVisual],
        },
      }
    }

    case 'SET_STYLE_PRESET': {
      if (!state.project) return state
      const preset = STYLE_PRESETS.find(p => p.id === action.payload)
      if (!preset) return state
      return {
        ...state,
        project: {
          ...state.project,
          styleConfig: { ...preset.value },
        },
      }
    }

    case 'SET_STYLE_CONFIG_ENVELOPE':
      if (!state.project) return state
      return {
        ...state,
        project: {
          ...state.project,
          styleConfig: action.payload,
        },
      }

    case 'UPDATE_STYLE_CONFIG': {
      if (!state.project) return state
      // Get current style config as envelope, or use default
      const currentEnvelope: StyleConfigEnvelope =
        state.project.styleConfig && 'style' in state.project.styleConfig
          ? (state.project.styleConfig as StyleConfigEnvelope)
          : DEFAULT_STYLE_CONFIG
      return {
        ...state,
        project: {
          ...state.project,
          styleConfig: {
            ...currentEnvelope,
            style: {
              ...currentEnvelope.style,
              ...action.payload,
            },
          },
        },
      }
    }

    case 'SET_VISUAL_PLAN':
      if (!state.project) return state
      return {
        ...state,
        project: {
          ...state.project,
          visualPlan: action.payload,
        },
      }

    case 'UPDATE_DRAFT':
      if (!state.project) return state
      return {
        ...state,
        project: {
          ...state.project,
          draftText: action.payload,
        },
      }

    case 'GENERATE_SAMPLE_DRAFT':
      if (!state.project) return state
      return {
        ...state,
        project: {
          ...state.project,
          draftText: SAMPLE_DRAFT_TEXT,
        },
      }

    case 'UPDATE_FINAL_TITLE':
      if (!state.project) return state
      return {
        ...state,
        project: {
          ...state.project,
          finalTitle: action.payload,
        },
      }

    case 'UPDATE_FINAL_SUBTITLE':
      if (!state.project) return state
      return {
        ...state,
        project: {
          ...state.project,
          finalSubtitle: action.payload,
        },
      }

    case 'UPDATE_CREDITS':
      if (!state.project) return state
      return {
        ...state,
        project: {
          ...state.project,
          creditsText: action.payload,
        },
      }

    case 'TOGGLE_EXPORT_MODAL':
      return {
        ...state,
        isExportModalOpen: !state.isExportModalOpen,
      }

    // AI Actions (T021)
    case 'START_AI_ACTION':
      return {
        ...state,
        aiAction: {
          inProgress: action.payload,
          error: null,
        },
      }

    case 'AI_ACTION_SUCCESS':
      return {
        ...state,
        aiAction: {
          inProgress: null,
          error: null,
        },
        aiPreview: {
          isOpen: true,
          preview: action.payload,
        },
      }

    case 'AI_ACTION_ERROR':
      return {
        ...state,
        aiAction: {
          inProgress: null,
          error: action.payload,
        },
      }

    // AI Preview Actions (T022)
    case 'APPLY_AI_PREVIEW': {
      if (!state.project || !state.aiPreview.preview) return state

      const preview = state.aiPreview.preview

      if (preview.type === 'clean-transcript') {
        // Apply cleaned transcript
        return {
          ...state,
          project: {
            ...state.project,
            transcriptText: preview.cleanedTranscript,
          },
          aiPreview: {
            isOpen: false,
            preview: null,
          },
        }
      }

      if (preview.type === 'suggest-outline') {
        // Add selected outline items
        const selectedItems = preview.items.filter((_, index) => preview.selected.has(index))
        const newOutlineItems = selectedItems.map((item, index) => ({
          id: generateId(),
          title: item.title,
          level: item.level,
          notes: item.notes,
          order: state.project!.outlineItems.length + index,
        }))
        return {
          ...state,
          project: {
            ...state.project,
            outlineItems: [...state.project.outlineItems, ...newOutlineItems],
          },
          aiPreview: {
            isOpen: false,
            preview: null,
          },
        }
      }

      if (preview.type === 'suggest-resources') {
        // Add selected resources
        const selectedResources = preview.resources.filter((_, index) => preview.selected.has(index))
        const newResources = selectedResources.map((resource, index) => ({
          id: generateId(),
          label: resource.label,
          urlOrNote: resource.url_or_note,
          order: state.project!.resources.length + index,
          resourceType: 'url_or_note' as const,
        }))
        return {
          ...state,
          project: {
            ...state.project,
            resources: [...state.project.resources, ...newResources],
          },
          aiPreview: {
            isOpen: false,
            preview: null,
          },
        }
      }

      return state
    }

    case 'DISCARD_AI_PREVIEW':
      return {
        ...state,
        aiPreview: {
          isOpen: false,
          preview: null,
        },
      }

    case 'TOGGLE_AI_PREVIEW_SELECTION': {
      if (!state.aiPreview.preview) return state
      const preview = state.aiPreview.preview

      if (preview.type === 'clean-transcript') {
        // Clean transcript doesn't have selection
        return state
      }

      // Toggle selection for outline or resources
      const newSelected = new Set(preview.selected)
      if (newSelected.has(action.payload)) {
        newSelected.delete(action.payload)
      } else {
        newSelected.add(action.payload)
      }

      return {
        ...state,
        aiPreview: {
          ...state.aiPreview,
          preview: {
            ...preview,
            selected: newSelected,
          } as AIPreviewData,
        },
      }
    }

    default:
      return state
  }
}

// Provider component
interface ProjectProviderProps {
  children: ReactNode
}

export function ProjectProvider({ children }: ProjectProviderProps) {
  // Hydrate initial state from localStorage if persistence is enabled
  const [state, dispatch] = useReducer(projectReducer, undefined, loadState)

  // Persist state to localStorage on changes
  useEffect(() => {
    saveState(state)
  }, [state])

  const createProject = useCallback(async (name: string, webinarType: WebinarType) => {
    dispatch({ type: 'SET_LOADING', payload: true })
    dispatch({ type: 'SET_ERROR', payload: null })

    try {
      const project = await apiCreateProject(name, webinarType)
      dispatch({ type: 'SET_PROJECT', payload: project })
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to create project'
      dispatch({ type: 'SET_ERROR', payload: message })
      dispatch({ type: 'SET_LOADING', payload: false })
      throw error
    }
  }, [])

  const openProject = useCallback(async (projectId: string) => {
    dispatch({ type: 'SET_LOADING', payload: true })
    dispatch({ type: 'SET_ERROR', payload: null })

    try {
      const project = await apiFetchProject(projectId)
      dispatch({ type: 'SET_PROJECT', payload: project })
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to load project'
      dispatch({ type: 'SET_ERROR', payload: message })
      dispatch({ type: 'SET_LOADING', payload: false })
      throw error
    }
  }, [])

  const saveProject = useCallback(async (): Promise<boolean> => {
    if (!state.project) {
      return true // Nothing to save
    }

    dispatch({ type: 'SET_SAVING', payload: true })
    dispatch({ type: 'SET_SAVE_ERROR', payload: null })

    try {
      const { id, createdAt: _createdAt, updatedAt: _updatedAt, ...projectData } = state.project
      void _createdAt
      void _updatedAt
      const updated = await apiUpdateProject(id, projectData)
      dispatch({ type: 'SET_PROJECT', payload: updated })
      dispatch({ type: 'SET_SAVING', payload: false })
      return true
    } catch (error) {
      // Check if project was deleted
      if (error instanceof ApiException && error.code === 'PROJECT_NOT_FOUND') {
        dispatch({ type: 'SET_SAVE_ERROR', payload: 'This project has been deleted. Redirecting to project list...' })
        dispatch({ type: 'SET_SAVING', payload: false })
        // Redirect to list after a short delay so user can see the message
        setTimeout(() => {
          dispatch({ type: 'CLEAR_PROJECT' })
          dispatch({ type: 'SET_VIEW', payload: 'list' })
        }, 2000)
        return false
      }

      const message = error instanceof Error ? error.message : 'Failed to save project'
      dispatch({ type: 'SET_SAVE_ERROR', payload: message })
      dispatch({ type: 'SET_SAVING', payload: false })
      return false
    }
  }, [state.project])

  const setActiveTab = useCallback((tab: TabIndex) => {
    dispatch({ type: 'SET_ACTIVE_TAB', payload: tab })
  }, [])

  const clearProject = useCallback(() => {
    dispatch({ type: 'CLEAR_PROJECT' })
  }, [])

  const goToList = useCallback(() => {
    dispatch({ type: 'CLEAR_PROJECT' })
    dispatch({ type: 'SET_VIEW', payload: 'list' })
  }, [])

  const clearSaveError = useCallback(() => {
    dispatch({ type: 'SET_SAVE_ERROR', payload: null })
  }, [])

  const uploadResourceFile = useCallback(async (file: File): Promise<Resource> => {
    if (!state.project) {
      throw new Error('No project loaded')
    }

    const uploadedResource = await apiUploadFile(state.project.id, file)

    // Convert the uploaded resource to our Resource type
    const resource: Resource = {
      id: uploadedResource.id,
      label: uploadedResource.label,
      order: uploadedResource.order,
      resourceType: 'file',
      urlOrNote: '',
      fileId: uploadedResource.fileId,
      fileName: uploadedResource.fileName,
      fileSize: uploadedResource.fileSize,
      mimeType: uploadedResource.mimeType,
      storagePath: uploadedResource.storagePath,
    }

    dispatch({ type: 'ADD_FILE_RESOURCE', payload: resource })

    return resource
  }, [state.project])

  const removeResourceFile = useCallback(async (resourceId: string, fileId: string): Promise<void> => {
    if (!state.project) {
      throw new Error('No project loaded')
    }

    // Delete file from server
    await apiDeleteFile(state.project.id, fileId)

    // Remove from local state
    dispatch({ type: 'REMOVE_RESOURCE', payload: resourceId })
  }, [state.project])

  const contextValue = useMemo<ProjectContextValue>(() => {
    const selectedVisuals = state.project?.visuals.filter(v => v.selected) ?? []
    const hasProject = state.project !== null

    return {
      state,
      dispatch,
      createProject,
      openProject,
      saveProject,
      setActiveTab,
      clearProject,
      goToList,
      clearSaveError,
      uploadResourceFile,
      removeResourceFile,
      selectedVisuals,
      hasProject,
    }
  }, [state, createProject, openProject, saveProject, setActiveTab, clearProject, goToList, clearSaveError, uploadResourceFile, removeResourceFile])

  return <ProjectContext.Provider value={contextValue}>{children}</ProjectContext.Provider>
}

// Custom hook
export function useProject(): ProjectContextValue {
  const context = useContext(ProjectContext)
  if (context === undefined) {
    throw new Error('useProject must be used within a ProjectProvider')
  }
  return context
}
