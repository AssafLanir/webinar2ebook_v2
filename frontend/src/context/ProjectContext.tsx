import type { ReactNode } from 'react'
import { createContext, useContext, useReducer, useMemo, useEffect, useCallback } from 'react'
import type {
  Project,
  ProjectState,
  ProjectAction,
  TabIndex,
  WebinarType,
  Visual,
} from '../types/project'
import { INITIAL_STATE, DEFAULT_STYLE_CONFIG } from '../types/project'
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
  ApiException,
} from '../services/api'

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
      }
      return {
        ...state,
        project: {
          ...state.project,
          resources: [...state.project.resources, newResource],
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

    case 'UPDATE_STYLE_CONFIG':
      if (!state.project) return state
      return {
        ...state,
        project: {
          ...state.project,
          styleConfig: {
            ...state.project.styleConfig,
            ...action.payload,
          },
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
      selectedVisuals,
      hasProject,
    }
  }, [state, createProject, openProject, saveProject, setActiveTab, clearProject, goToList, clearSaveError])

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
