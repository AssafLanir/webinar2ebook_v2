/**
 * Tab 4: Final Assembly + Preview + Export
 *
 * Displays:
 * - Final metadata editing (title, subtitle, credits)
 * - HTML preview of assembled ebook with images
 * - PDF export functionality
 */

import { useState, useCallback } from 'react'
import { useProject } from '../../context/ProjectContext'
import { Card } from '../common/Card'
import { MetadataForm } from './MetadataForm'
import { PreviewPanel } from './PreviewPanel'
import { ExportActions } from './ExportActions'

export function Tab4Content() {
  const { state, dispatch, saveProject } = useProject()
  const { project, isSaving } = state
  const [hasPreviewContent, setHasPreviewContent] = useState(false)
  const [previewRefreshTrigger, setPreviewRefreshTrigger] = useState(0)
  const [saveSuccess, setSaveSuccess] = useState(false)

  // Refresh preview after metadata changes
  const refreshPreview = useCallback(() => {
    setPreviewRefreshTrigger((prev) => prev + 1)
  }, [])

  // Manual save handler
  const handleSave = useCallback(async () => {
    const success = await saveProject()
    if (success) {
      setSaveSuccess(true)
      setTimeout(() => setSaveSuccess(false), 2000)
      // Refresh preview after save to show updated metadata
      refreshPreview()
    }
  }, [saveProject, refreshPreview])

  if (!project) return null

  const handleTitleChange = (value: string) => {
    dispatch({ type: 'UPDATE_FINAL_TITLE', payload: value })
  }

  const handleSubtitleChange = (value: string) => {
    dispatch({ type: 'UPDATE_FINAL_SUBTITLE', payload: value })
  }

  const handleCreditsChange = (value: string) => {
    dispatch({ type: 'UPDATE_CREDITS', payload: value })
  }

  return (
    <div className="space-y-6">
      {/* Metadata Section */}
      <Card
        title="Final Metadata"
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
                  <circle
                    className="opacity-25"
                    cx="12"
                    cy="12"
                    r="10"
                    stroke="currentColor"
                    strokeWidth="4"
                  />
                  <path
                    className="opacity-75"
                    fill="currentColor"
                    d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
                  />
                </svg>
                Saving...
              </>
            ) : saveSuccess ? (
              <>
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M5 13l4 4L19 7"
                  />
                </svg>
                Saved
              </>
            ) : (
              <>
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M8 7H5a2 2 0 00-2 2v9a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-3m-1 4l-3 3m0 0l-3-3m3 3V4"
                  />
                </svg>
                Save
              </>
            )}
          </button>
        }
      >
        <p className="text-sm text-slate-400 mb-4">
          Set the final title, subtitle, and credits for your ebook cover page.
        </p>
        <MetadataForm
          finalTitle={project.finalTitle}
          finalSubtitle={project.finalSubtitle}
          creditsText={project.creditsText}
          onTitleChange={handleTitleChange}
          onSubtitleChange={handleSubtitleChange}
          onCreditsChange={handleCreditsChange}
        />
      </Card>

      {/* Preview Section */}
      <Card title="Ebook Preview">
        <p className="text-sm text-slate-400 mb-4">
          Preview of your assembled ebook with cover page, table of contents, chapters, and
          assigned images.
        </p>
        <PreviewPanel
          projectId={project.id}
          includeImages={true}
          onContentChange={setHasPreviewContent}
          refreshTrigger={previewRefreshTrigger}
        />
      </Card>

      {/* Export Section */}
      <Card title="Export">
        <ExportActions
          projectId={project.id}
          canExport={hasPreviewContent}
          disabledMessage="Generate a draft in Tab 3 first"
        />
        {!hasPreviewContent && (
          <p className="mt-3 text-sm text-yellow-400/80 flex items-center gap-2">
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
              />
            </svg>
            Generate a draft in Tab 3 to enable PDF export.
          </p>
        )}
      </Card>
    </div>
  )
}
