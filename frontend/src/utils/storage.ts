import type { ProjectState, Project } from '../types/project'
import { INITIAL_STATE } from '../types/project'

const STORAGE_KEY = 'webinar2ebook_project'

/**
 * Stored state structure for localStorage
 */
interface StoredState {
  project: Project | null
  activeTab: ProjectState['activeTab']
}

/**
 * Check if localStorage persistence is enabled
 * Opt-in via VITE_ENABLE_PERSISTENCE environment variable
 */
export function isPersistenceEnabled(): boolean {
  return import.meta.env.VITE_ENABLE_PERSISTENCE === 'true'
}

/**
 * Load project state from localStorage
 * Returns INITIAL_STATE if no saved state or persistence is disabled
 */
export function loadState(): ProjectState {
  if (!isPersistenceEnabled()) {
    return INITIAL_STATE
  }

  try {
    const serialized = localStorage.getItem(STORAGE_KEY)
    if (!serialized) {
      return INITIAL_STATE
    }

    const stored: StoredState = JSON.parse(serialized)

    return {
      ...INITIAL_STATE,
      project: stored.project,
      activeTab: stored.activeTab,
    }
  } catch (error) {
    console.warn('Failed to load state from localStorage:', error)
    return INITIAL_STATE
  }
}

/**
 * Save project state to localStorage
 * Only saves if persistence is enabled
 */
export function saveState(state: ProjectState): void {
  if (!isPersistenceEnabled()) {
    return
  }

  try {
    const stored: StoredState = {
      project: state.project,
      activeTab: state.activeTab,
    }

    localStorage.setItem(STORAGE_KEY, JSON.stringify(stored))
  } catch (error) {
    console.warn('Failed to save state to localStorage:', error)
  }
}

/**
 * Clear saved state from localStorage
 */
export function clearState(): void {
  try {
    localStorage.removeItem(STORAGE_KEY)
  } catch (error) {
    console.warn('Failed to clear state from localStorage:', error)
  }
}
