import { describe, it, expect } from 'vitest'
import type { ProjectState, Project } from '../../src/types/project'
import type { Edition, Fidelity, Theme, Coverage } from '../../src/types/edition'

// Import the reducer directly for testing
// We need to export it from ProjectContext first
import { projectReducer } from '../../src/context/ProjectContext'

// Helper to create a minimal project state for testing
function createTestState(projectOverrides: Partial<Project> = {}): ProjectState {
  const project: Project = {
    id: 'test-project-1',
    name: 'Test Project',
    webinarType: 'interview',
    createdAt: '2024-01-01T00:00:00Z',
    updatedAt: '2024-01-01T00:00:00Z',
    edition: 'qa',
    fidelity: 'faithful',
    themes: [],
    canonical_transcript: null,
    canonical_transcript_hash: null,
    transcriptText: '',
    outlineItems: [],
    resources: [],
    visuals: [],
    draftText: '',
    styleConfig: null,
    visualPlan: null,
    finalTitle: '',
    finalSubtitle: '',
    creditsText: '',
    ...projectOverrides,
  }

  return {
    view: 'workspace',
    projectList: [],
    project,
    activeTab: 1,
    isExportModalOpen: false,
    isLoading: false,
    isSaving: false,
    saveError: null,
    error: null,
    aiAction: { inProgress: null, error: null },
    aiPreview: { isOpen: false, preview: null },
  }
}

// Helper to create a test theme
function createTestTheme(overrides: Partial<Theme> = {}): Theme {
  return {
    id: 'theme-1',
    title: 'Test Theme',
    one_liner: 'A test theme for unit testing',
    keywords: ['test', 'unit'],
    coverage: 'medium',
    supporting_segments: [],
    include_in_generation: true,
    ...overrides,
  }
}

describe('Edition Reducer Actions', () => {
  describe('SET_EDITION', () => {
    it('should set edition to ideas', () => {
      const state = createTestState({ edition: 'qa' })
      const result = projectReducer(state, { type: 'SET_EDITION', payload: 'ideas' })
      expect(result.project?.edition).toBe('ideas')
    })

    it('should set edition to qa', () => {
      const state = createTestState({ edition: 'ideas' })
      const result = projectReducer(state, { type: 'SET_EDITION', payload: 'qa' })
      expect(result.project?.edition).toBe('qa')
    })

    it('should return state unchanged when project is null', () => {
      const state: ProjectState = { ...createTestState(), project: null }
      const result = projectReducer(state, { type: 'SET_EDITION', payload: 'ideas' })
      expect(result).toBe(state)
    })
  })

  describe('SET_FIDELITY', () => {
    it('should set fidelity to verbatim', () => {
      const state = createTestState({ fidelity: 'faithful' })
      const result = projectReducer(state, { type: 'SET_FIDELITY', payload: 'verbatim' })
      expect(result.project?.fidelity).toBe('verbatim')
    })

    it('should set fidelity to faithful', () => {
      const state = createTestState({ fidelity: 'verbatim' })
      const result = projectReducer(state, { type: 'SET_FIDELITY', payload: 'faithful' })
      expect(result.project?.fidelity).toBe('faithful')
    })

    it('should return state unchanged when project is null', () => {
      const state: ProjectState = { ...createTestState(), project: null }
      const result = projectReducer(state, { type: 'SET_FIDELITY', payload: 'verbatim' })
      expect(result).toBe(state)
    })
  })

  describe('SET_THEMES', () => {
    it('should set themes array', () => {
      const state = createTestState({ themes: [] })
      const newThemes: Theme[] = [
        createTestTheme({ id: 'theme-1', title: 'First Theme' }),
        createTestTheme({ id: 'theme-2', title: 'Second Theme' }),
      ]
      const result = projectReducer(state, { type: 'SET_THEMES', payload: newThemes })
      expect(result.project?.themes).toHaveLength(2)
      expect(result.project?.themes[0].title).toBe('First Theme')
      expect(result.project?.themes[1].title).toBe('Second Theme')
    })

    it('should replace existing themes', () => {
      const existingThemes: Theme[] = [createTestTheme({ id: 'old-theme' })]
      const state = createTestState({ themes: existingThemes })
      const newThemes: Theme[] = [createTestTheme({ id: 'new-theme', title: 'New Theme' })]
      const result = projectReducer(state, { type: 'SET_THEMES', payload: newThemes })
      expect(result.project?.themes).toHaveLength(1)
      expect(result.project?.themes[0].id).toBe('new-theme')
    })

    it('should return state unchanged when project is null', () => {
      const state: ProjectState = { ...createTestState(), project: null }
      const result = projectReducer(state, { type: 'SET_THEMES', payload: [] })
      expect(result).toBe(state)
    })
  })

  describe('UPDATE_THEME', () => {
    it('should update theme title', () => {
      const themes: Theme[] = [createTestTheme({ id: 'theme-1', title: 'Original Title' })]
      const state = createTestState({ themes })
      const result = projectReducer(state, {
        type: 'UPDATE_THEME',
        payload: { id: 'theme-1', updates: { title: 'Updated Title' } },
      })
      expect(result.project?.themes[0].title).toBe('Updated Title')
    })

    it('should update theme coverage', () => {
      const themes: Theme[] = [createTestTheme({ id: 'theme-1', coverage: 'weak' })]
      const state = createTestState({ themes })
      const result = projectReducer(state, {
        type: 'UPDATE_THEME',
        payload: { id: 'theme-1', updates: { coverage: 'strong' } },
      })
      expect(result.project?.themes[0].coverage).toBe('strong')
    })

    it('should update include_in_generation flag', () => {
      const themes: Theme[] = [createTestTheme({ id: 'theme-1', include_in_generation: true })]
      const state = createTestState({ themes })
      const result = projectReducer(state, {
        type: 'UPDATE_THEME',
        payload: { id: 'theme-1', updates: { include_in_generation: false } },
      })
      expect(result.project?.themes[0].include_in_generation).toBe(false)
    })

    it('should only update the specified theme', () => {
      const themes: Theme[] = [
        createTestTheme({ id: 'theme-1', title: 'Theme 1' }),
        createTestTheme({ id: 'theme-2', title: 'Theme 2' }),
      ]
      const state = createTestState({ themes })
      const result = projectReducer(state, {
        type: 'UPDATE_THEME',
        payload: { id: 'theme-1', updates: { title: 'Updated Theme 1' } },
      })
      expect(result.project?.themes[0].title).toBe('Updated Theme 1')
      expect(result.project?.themes[1].title).toBe('Theme 2')
    })

    it('should return state unchanged when theme not found', () => {
      const themes: Theme[] = [createTestTheme({ id: 'theme-1' })]
      const state = createTestState({ themes })
      const result = projectReducer(state, {
        type: 'UPDATE_THEME',
        payload: { id: 'nonexistent', updates: { title: 'New Title' } },
      })
      expect(result.project?.themes).toEqual(themes)
    })

    it('should return state unchanged when project is null', () => {
      const state: ProjectState = { ...createTestState(), project: null }
      const result = projectReducer(state, {
        type: 'UPDATE_THEME',
        payload: { id: 'theme-1', updates: { title: 'New Title' } },
      })
      expect(result).toBe(state)
    })
  })

  describe('REMOVE_THEME', () => {
    it('should remove theme by id', () => {
      const themes: Theme[] = [
        createTestTheme({ id: 'theme-1' }),
        createTestTheme({ id: 'theme-2' }),
      ]
      const state = createTestState({ themes })
      const result = projectReducer(state, { type: 'REMOVE_THEME', payload: 'theme-1' })
      expect(result.project?.themes).toHaveLength(1)
      expect(result.project?.themes[0].id).toBe('theme-2')
    })

    it('should return unchanged state when theme not found', () => {
      const themes: Theme[] = [createTestTheme({ id: 'theme-1' })]
      const state = createTestState({ themes })
      const result = projectReducer(state, { type: 'REMOVE_THEME', payload: 'nonexistent' })
      expect(result.project?.themes).toHaveLength(1)
    })

    it('should return state unchanged when project is null', () => {
      const state: ProjectState = { ...createTestState(), project: null }
      const result = projectReducer(state, { type: 'REMOVE_THEME', payload: 'theme-1' })
      expect(result).toBe(state)
    })
  })

  describe('REORDER_THEMES', () => {
    it('should reorder themes by id array', () => {
      const themes: Theme[] = [
        createTestTheme({ id: 'theme-1', title: 'First' }),
        createTestTheme({ id: 'theme-2', title: 'Second' }),
        createTestTheme({ id: 'theme-3', title: 'Third' }),
      ]
      const state = createTestState({ themes })
      const result = projectReducer(state, {
        type: 'REORDER_THEMES',
        payload: ['theme-3', 'theme-1', 'theme-2'],
      })
      expect(result.project?.themes[0].id).toBe('theme-3')
      expect(result.project?.themes[1].id).toBe('theme-1')
      expect(result.project?.themes[2].id).toBe('theme-2')
    })

    it('should filter out nonexistent theme ids', () => {
      const themes: Theme[] = [
        createTestTheme({ id: 'theme-1' }),
        createTestTheme({ id: 'theme-2' }),
      ]
      const state = createTestState({ themes })
      const result = projectReducer(state, {
        type: 'REORDER_THEMES',
        payload: ['nonexistent', 'theme-2', 'theme-1'],
      })
      expect(result.project?.themes).toHaveLength(2)
      expect(result.project?.themes[0].id).toBe('theme-2')
      expect(result.project?.themes[1].id).toBe('theme-1')
    })

    it('should return state unchanged when project is null', () => {
      const state: ProjectState = { ...createTestState(), project: null }
      const result = projectReducer(state, {
        type: 'REORDER_THEMES',
        payload: ['theme-1', 'theme-2'],
      })
      expect(result).toBe(state)
    })
  })
})
