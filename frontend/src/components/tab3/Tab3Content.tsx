import { useState, useMemo, useCallback, useRef, useEffect } from 'react'
import { useProject } from '../../context/ProjectContext'
import { Card } from '../common/Card'
import { Select } from '../common/Select'
import { Button } from '../common/Button'
import { StyleControls } from './StyleControls'
import { DraftEditor } from './DraftEditor'
import { GenerateProgress } from './GenerateProgress'
import { DraftPreviewModal } from './DraftPreviewModal'
import { useDraftGeneration } from '../../hooks/useDraftGeneration'
import { STYLE_PRESETS } from '../../constants/stylePresets'
import type { StyleConfig, StyleConfigEnvelope } from '../../types/style'
import type { DraftGenerateRequest } from '../../types/draft'
import { DEFAULT_STYLE_CONFIG } from '../../types/project'

// Validation constants
const MIN_TRANSCRIPT_LENGTH = 500
const MIN_OUTLINE_ITEMS = 3

export function Tab3Content() {
  const { state, dispatch, saveProject } = useProject()
  const { project, isSaving } = state
  const [showCustomize, setShowCustomize] = useState(false)
  const [isCancelling, setIsCancelling] = useState(false)
  const [showPreviewModal, setShowPreviewModal] = useState(false)
  const [saveSuccess, setSaveSuccess] = useState(false)
  const draftEditorRef = useRef<HTMLDivElement>(null)
  const pendingSaveAfterApply = useRef(false)

  // Draft generation hook
  const {
    state: generationState,
    startGeneration,
    cancelGeneration,
    reset: resetGeneration,
    isGenerating,
  } = useDraftGeneration()

  // Save project after applying draft (watches for state update, then saves)
  useEffect(() => {
    if (pendingSaveAfterApply.current && !isSaving) {
      pendingSaveAfterApply.current = false
      saveProject()
    }
  }, [project?.draftText, project?.visualPlan, isSaving, saveProject])

  // Get current style config as envelope (must compute before hooks that depend on it)
  const styleEnvelope: StyleConfigEnvelope = useMemo(() => {
    if (!project) return DEFAULT_STYLE_CONFIG
    return project.styleConfig && 'style' in project.styleConfig
      ? (project.styleConfig as StyleConfigEnvelope)
      : DEFAULT_STYLE_CONFIG
  }, [project])

  const currentPresetId = styleEnvelope.preset_id ?? 'default_webinar_ebook_v1'

  const presetOptions = useMemo(() =>
    STYLE_PRESETS.map(preset => ({
      value: preset.id,
      label: preset.label,
    })),
    []
  )

  // Validation
  const validation = useMemo(() => {
    const transcriptLength = project?.transcriptText?.length ?? 0
    const outlineCount = project?.outlineItems?.length ?? 0

    const errors: string[] = []
    if (transcriptLength < MIN_TRANSCRIPT_LENGTH) {
      errors.push(`Transcript must be at least ${MIN_TRANSCRIPT_LENGTH} characters (currently ${transcriptLength})`)
    }
    if (outlineCount < MIN_OUTLINE_ITEMS) {
      errors.push(`Outline must have at least ${MIN_OUTLINE_ITEMS} items (currently ${outlineCount})`)
    }

    return {
      isValid: errors.length === 0,
      errors,
      transcriptLength,
      outlineCount,
    }
  }, [project?.transcriptText, project?.outlineItems])

  const handlePresetChange = useCallback((presetId: string) => {
    dispatch({ type: 'SET_STYLE_PRESET', payload: presetId })
    setShowCustomize(false)
  }, [dispatch])

  const handleStyleChange = useCallback((updates: Partial<StyleConfig>) => {
    dispatch({ type: 'UPDATE_STYLE_CONFIG', payload: updates })
  }, [dispatch])

  const handleDraftChange = useCallback((value: string) => {
    dispatch({ type: 'UPDATE_DRAFT', payload: value })
  }, [dispatch])

  // Manual save handler
  const handleSave = useCallback(async () => {
    const success = await saveProject()
    if (success) {
      setSaveSuccess(true)
      setTimeout(() => setSaveSuccess(false), 2000)
    }
  }, [saveProject])

  // Start AI draft generation
  const handleGenerateDraft = useCallback(async () => {
    if (!validation.isValid || !project) return

    // Build request payload
    const request: DraftGenerateRequest = {
      transcript: project.transcriptText,
      outline: project.outlineItems.map(item => ({
        id: item.id,
        title: item.title,
        level: item.level,
        notes: item.notes,
        order: item.order,
      })),
      resources: project.resources.map(r => ({
        id: r.id,
        label: r.label,
        url_or_note: r.urlOrNote,
      })),
      style_config: styleEnvelope,
    }

    await startGeneration(request)
  }, [validation.isValid, project, styleEnvelope, startGeneration])

  // Cancel generation
  const handleCancelGeneration = useCallback(async () => {
    setIsCancelling(true)
    try {
      await cancelGeneration()
    } finally {
      setIsCancelling(false)
    }
  }, [cancelGeneration])

  // Handle generation completion - show preview modal
  const handleViewResults = useCallback(() => {
    if (generationState.draftMarkdown) {
      setShowPreviewModal(true)
    }
  }, [generationState.draftMarkdown])

  // Apply generated draft to project
  const handleApplyDraft = useCallback(() => {
    if (generationState.draftMarkdown) {
      dispatch({ type: 'UPDATE_DRAFT', payload: generationState.draftMarkdown })

      // Also save visual plan if available
      if (generationState.visualPlan) {
        dispatch({ type: 'SET_VISUAL_PLAN', payload: generationState.visualPlan })
      }

      // Flag to trigger save after state updates
      pendingSaveAfterApply.current = true
    }
    setShowPreviewModal(false)
    resetGeneration()
  }, [generationState.draftMarkdown, generationState.visualPlan, dispatch, resetGeneration])

  // Apply and scroll to editor
  const handleApplyAndEdit = useCallback(() => {
    if (generationState.draftMarkdown) {
      dispatch({ type: 'UPDATE_DRAFT', payload: generationState.draftMarkdown })

      if (generationState.visualPlan) {
        dispatch({ type: 'SET_VISUAL_PLAN', payload: generationState.visualPlan })
      }

      // Flag to trigger save after state updates
      pendingSaveAfterApply.current = true
    }
    setShowPreviewModal(false)
    resetGeneration()

    // Scroll to editor after a brief delay to let modal close
    setTimeout(() => {
      draftEditorRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
      // Try to focus the textarea inside
      const textarea = draftEditorRef.current?.querySelector('textarea')
      if (textarea) {
        textarea.focus()
      }
    }, 100)
  }, [generationState.draftMarkdown, generationState.visualPlan, dispatch, resetGeneration])

  // Discard generated draft
  const handleDiscardDraft = useCallback(() => {
    setShowPreviewModal(false)
    resetGeneration()
  }, [resetGeneration])

  // Retry generation after failure
  const handleRetry = useCallback(() => {
    resetGeneration()
    handleGenerateDraft()
  }, [resetGeneration, handleGenerateDraft])

  const currentPreset = STYLE_PRESETS.find(p => p.id === currentPresetId)

  // Early return after all hooks
  if (!project) return null

  // Determine if we should show the generation UI
  const showGenerationUI = isGenerating || generationState.phase === 'completed' || generationState.phase === 'failed' || generationState.phase === 'cancelled'

  return (
    <div className="space-y-6">
      <Card title="Style Configuration">
        <p className="text-sm text-slate-400 mb-4">
          Select a preset or customize the style settings for your ebook generation.
        </p>

        <div className="space-y-4">
          <Select
            label="Style Preset"
            value={currentPresetId}
            onChange={handlePresetChange}
            options={presetOptions}
          />

          {currentPreset && (
            <p className="text-sm text-slate-500 italic">
              {currentPreset.description}
            </p>
          )}

          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => setShowCustomize(!showCustomize)}
              className="text-sm text-cyan-400 hover:text-cyan-300 underline"
            >
              {showCustomize ? 'Hide customization' : 'Customize style settings'}
            </button>
          </div>

          {showCustomize && (
            <div className="mt-4 pt-4 border-t border-slate-700">
              <p className="text-sm text-slate-400 mb-3">
                Adjust individual settings to override the preset defaults:
              </p>
              <StyleControls
                config={styleEnvelope.style}
                onChange={handleStyleChange}
              />
            </div>
          )}
        </div>
      </Card>

      {/* AI Generation Section */}
      <Card title="AI Draft Generation">
        {/* Validation errors */}
        {!validation.isValid && (
          <div className="mb-4 p-3 bg-yellow-500/10 border border-yellow-500/30 rounded-lg">
            <p className="text-sm font-medium text-yellow-400 mb-2">
              Complete the following before generating:
            </p>
            <ul className="text-sm text-yellow-400/80 list-disc list-inside space-y-1">
              {validation.errors.map((error, i) => (
                <li key={i}>{error}</li>
              ))}
            </ul>
          </div>
        )}

        {/* Generation progress */}
        {showGenerationUI ? (
          <div className="space-y-4">
            <GenerateProgress
              state={generationState}
              isCancelling={isCancelling}
              onCancel={handleCancelGeneration}
              onRetry={handleRetry}
              onViewPartial={handleViewResults}
            />

            {/* View results button when completed */}
            {generationState.phase === 'completed' && generationState.draftMarkdown && (
              <div className="flex justify-center">
                <Button variant="primary" onClick={handleViewResults}>
                  View Generated Draft
                </Button>
              </div>
            )}
          </div>
        ) : (
          <div className="space-y-4">
            <p className="text-sm text-slate-400">
              Generate an AI-powered ebook draft based on your transcript, outline, and style settings.
            </p>
            <Button
              variant="primary"
              onClick={handleGenerateDraft}
              disabled={!validation.isValid}
            >
              <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M13 10V3L4 14h7v7l9-11h-7z"
                />
              </svg>
              Generate AI Draft
            </Button>
          </div>
        )}
      </Card>

      {/* Manual Draft Editor */}
      <div ref={draftEditorRef}>
        <Card
          title="Draft Content"
          headerAction={
            <button
              type="button"
              onClick={handleSave}
              disabled={isSaving}
              className={`flex items-center gap-1.5 px-3 py-1.5 text-sm rounded-lg transition-colors ${
                saveSuccess
                  ? 'bg-green-500/20 text-green-400'
                  : isSaving
                    ? 'bg-slate-700 text-slate-400 cursor-not-allowed'
                    : 'bg-cyan-500/20 text-cyan-400 hover:bg-cyan-500/30'
              }`}
            >
              {isSaving ? (
                <>
                  <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                  </svg>
                  Saving...
                </>
              ) : saveSuccess ? (
                <>
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                  </svg>
                  Saved
                </>
              ) : (
                <>
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7H5a2 2 0 00-2 2v9a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-3m-1 4l-3 3m0 0l-3-3m3 3V4" />
                  </svg>
                  Save
                </>
              )}
            </button>
          }
        >
          <DraftEditor
            value={project.draftText}
            onChange={handleDraftChange}
            onGenerate={handleGenerateDraft}
          />
        </Card>
      </div>

      {/* Preview Modal */}
      <DraftPreviewModal
        isOpen={showPreviewModal}
        draftMarkdown={generationState.draftMarkdown ?? ''}
        projectTitle={project.name}
        projectId={project.id}
        stats={generationState.stats}
        onApply={handleApplyDraft}
        onApplyAndEdit={handleApplyAndEdit}
        onDiscard={handleDiscardDraft}
      />
    </div>
  )
}
