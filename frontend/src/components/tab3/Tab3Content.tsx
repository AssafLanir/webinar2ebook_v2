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
import { QAPanel } from './QAPanel'
import { STYLE_PRESETS } from '../../constants/stylePresets'
import { downloadAsMarkdown, downloadAsText } from '../../utils/draftExport'
import type { StyleConfig, StyleConfigEnvelope, TotalLengthPreset } from '../../types/style'
import { computeWordsPerChapter, TOTAL_LENGTH_WORD_TARGETS } from '../../types/style'
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
  const [draftCopied, setDraftCopied] = useState(false)
  const [showDraftDownloadMenu, setShowDraftDownloadMenu] = useState(false)
  const [showRegenerationWarning, setShowRegenerationWarning] = useState(false)
  const draftEditorRef = useRef<HTMLDivElement>(null)
  const draftDownloadMenuRef = useRef<HTMLDivElement>(null)
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

  // Close download menu when clicking outside
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (draftDownloadMenuRef.current && !draftDownloadMenuRef.current.contains(event.target as Node)) {
        setShowDraftDownloadMenu(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

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
    const bookFormat = styleEnvelope.style.book_format
    const isInterviewQA = bookFormat === 'interview_qa'

    const errors: string[] = []
    if (transcriptLength < MIN_TRANSCRIPT_LENGTH) {
      errors.push(`Transcript must be at least ${MIN_TRANSCRIPT_LENGTH} characters (currently ${transcriptLength})`)
    }
    // Interview Q&A format allows empty outline (generates single flowing Q&A document)
    if (outlineCount < MIN_OUTLINE_ITEMS && !isInterviewQA) {
      errors.push(`Outline must have at least ${MIN_OUTLINE_ITEMS} items (currently ${outlineCount})`)
    }

    return {
      isValid: errors.length === 0,
      errors,
      transcriptLength,
      outlineCount,
    }
  }, [project?.transcriptText, project?.outlineItems, styleEnvelope.style.book_format])

  // Compute words per chapter hint
  const lengthHint = useMemo(() => {
    const chapterCount = validation.outlineCount
    if (chapterCount <= 0) return null

    const preset = (styleEnvelope.style.total_length_preset ?? 'standard') as TotalLengthPreset
    const customWords = styleEnvelope.style.total_target_words

    let totalWords: number
    if (preset === 'custom') {
      totalWords = customWords ?? 5000
    } else {
      totalWords = TOTAL_LENGTH_WORD_TARGETS[preset as Exclude<TotalLengthPreset, 'custom'>]
    }

    const wordsPerChapter = computeWordsPerChapter(preset, chapterCount, customWords)

    return {
      chapterCount,
      totalWords,
      wordsPerChapter,
    }
  }, [validation.outlineCount, styleEnvelope.style.total_length_preset, styleEnvelope.style.total_target_words])

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

  // Copy draft to clipboard
  const handleCopyDraft = useCallback(async () => {
    if (!project?.draftText) return
    try {
      await navigator.clipboard.writeText(project.draftText)
      setDraftCopied(true)
      setTimeout(() => setDraftCopied(false), 2000)
    } catch (err) {
      console.error('Failed to copy draft:', err)
    }
  }, [project?.draftText])

  // Download draft handlers
  const handleDownloadMarkdown = useCallback(() => {
    if (!project?.draftText) return
    downloadAsMarkdown(project.draftText, project.name, project.id)
    setShowDraftDownloadMenu(false)
  }, [project?.draftText, project?.name, project?.id])

  const handleDownloadText = useCallback(() => {
    if (!project?.draftText) return
    downloadAsText(project.draftText, project.name, project.id)
    setShowDraftDownloadMenu(false)
  }, [project?.draftText, project?.name, project?.id])

  // Check if there are existing visual assignments (T048)
  const hasExistingAssignments = useMemo(() => {
    const assignments = project?.visualPlan?.assignments ?? []
    return assignments.length > 0
  }, [project?.visualPlan?.assignments])

  // Start AI draft generation (with warning check)
  const handleGenerateClick = useCallback(() => {
    if (!validation.isValid || !project) return

    // If there are existing assignments, show warning first (T048)
    if (hasExistingAssignments) {
      setShowRegenerationWarning(true)
      return
    }

    // No existing assignments, proceed directly
    handleGenerateDraftConfirmed()
  }, [validation.isValid, project, hasExistingAssignments])

  // Actually start generation (after confirmation if needed)
  const handleGenerateDraftConfirmed = useCallback(async () => {
    if (!validation.isValid || !project) return
    setShowRegenerationWarning(false)

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

  // Cancel regeneration warning
  const handleCancelRegeneration = useCallback(() => {
    setShowRegenerationWarning(false)
  }, [])

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
    handleGenerateDraftConfirmed()
  }, [resetGeneration, handleGenerateDraftConfirmed])

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
              {/* Words per chapter hint */}
              {lengthHint && (
                <p className="mt-4 text-xs text-slate-500">
                  Outline has {lengthHint.chapterCount} chapters → targeting ~{lengthHint.wordsPerChapter.toLocaleString()} words/chapter (approx.)
                </p>
              )}
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
              onClick={handleGenerateClick}
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
            <div className="flex items-center gap-2">
              {/* Copy button */}
              <button
                type="button"
                onClick={handleCopyDraft}
                disabled={!project?.draftText}
                title={!project?.draftText ? 'No draft to copy' : 'Copy to clipboard'}
                className={`flex items-center gap-1.5 px-3 py-1.5 text-sm rounded-lg transition-colors ${
                  !project?.draftText
                    ? 'bg-slate-800 text-slate-500 cursor-not-allowed'
                    : draftCopied
                      ? 'bg-green-500/20 text-green-400'
                      : 'bg-slate-700 text-slate-300 hover:bg-slate-600'
                }`}
              >
                {draftCopied ? (
                  <>
                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                    </svg>
                    Copied!
                  </>
                ) : (
                  <>
                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
                    </svg>
                    Copy
                  </>
                )}
              </button>

              {/* Download dropdown */}
              <div className="relative" ref={draftDownloadMenuRef}>
                <button
                  type="button"
                  onClick={() => setShowDraftDownloadMenu(!showDraftDownloadMenu)}
                  disabled={!project?.draftText}
                  title={!project?.draftText ? 'No draft to download' : 'Download draft'}
                  className={`flex items-center gap-1.5 px-3 py-1.5 text-sm rounded-lg transition-colors ${
                    !project?.draftText
                      ? 'bg-slate-800 text-slate-500 cursor-not-allowed'
                      : 'bg-slate-700 text-slate-300 hover:bg-slate-600'
                  }`}
                >
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                  </svg>
                  Download
                  <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                  </svg>
                </button>

                {showDraftDownloadMenu && project?.draftText && (
                  <div className="absolute right-0 mt-1 w-44 bg-slate-700 rounded-lg shadow-xl border border-slate-600 overflow-hidden z-10">
                    <button
                      onClick={handleDownloadMarkdown}
                      className="w-full px-4 py-2 text-left text-sm text-slate-200 hover:bg-slate-600 transition-colors"
                    >
                      Markdown (.md)
                    </button>
                    <button
                      onClick={handleDownloadText}
                      className="w-full px-4 py-2 text-left text-sm text-slate-200 hover:bg-slate-600 transition-colors"
                    >
                      Plain text (.txt)
                    </button>
                  </div>
                )}
              </div>

              {/* Save button */}
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
            </div>
          }
        >
          <DraftEditor
            value={project.draftText}
            onChange={handleDraftChange}
            onGenerate={handleGenerateClick}
          />
        </Card>
      </div>

      {/* QA Panel - T026 */}
      <QAPanel
        projectId={project.id}
        hasDraft={!!project.draftText && project.draftText.length > 100}
      />

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

      {/* Regeneration Warning Modal (T048) */}
      {showRegenerationWarning && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50">
          <div className="bg-slate-800 rounded-lg shadow-xl max-w-md w-full mx-4 border border-slate-700">
            <div className="px-6 py-4 border-b border-slate-700">
              <h3 className="text-lg font-semibold text-white flex items-center gap-2">
                <svg className="w-5 h-5 text-yellow-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                </svg>
                Regenerate Draft?
              </h3>
            </div>
            <div className="px-6 py-4">
              <p className="text-slate-300 mb-3">
                You have existing visual assignments in Tab 2. Regenerating the draft will:
              </p>
              <ul className="text-sm text-slate-400 list-disc list-inside space-y-1 mb-4">
                <li>Create a new visual opportunity plan</li>
                <li>Clear all current visual assignments</li>
                <li>Your uploaded images will remain in the library</li>
              </ul>
              <p className="text-sm text-slate-500">
                You'll need to reassign images to the new opportunities after regeneration.
              </p>
            </div>
            <div className="px-6 py-4 border-t border-slate-700 flex justify-end gap-3">
              <button
                onClick={handleCancelRegeneration}
                className="px-4 py-2 text-sm text-slate-300 hover:bg-slate-700 rounded-lg transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleGenerateDraftConfirmed}
                className="px-4 py-2 text-sm bg-yellow-500 text-slate-900 hover:bg-yellow-400 rounded-lg transition-colors font-medium"
              >
                Regenerate Anyway
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
