/**
 * ExportActions Component
 *
 * Provides the PDF and EPUB export UI including:
 * - Download PDF button
 * - Download EPUB button
 * - Progress bar during generation
 * - Cancel button when generating
 * - Error display with retry
 */

import { useCallback } from 'react'
import { useExport } from '../../hooks/useExport'

interface ExportActionsProps {
  projectId: string
  /** Whether the export button should be enabled */
  canExport: boolean
  /** Message to show when export is disabled */
  disabledMessage?: string
}

export function ExportActions({ projectId, canExport, disabledMessage }: ExportActionsProps) {
  const { state, startExport, cancelExport, download, reset, isExporting, format } = useExport()

  const handleExportPdf = useCallback(() => {
    if (canExport && !isExporting) {
      startExport(projectId, 'pdf')
    }
  }, [canExport, isExporting, startExport, projectId])

  const handleExportEpub = useCallback(() => {
    if (canExport && !isExporting) {
      startExport(projectId, 'epub')
    }
  }, [canExport, isExporting, startExport, projectId])

  const handleCancel = useCallback(() => {
    cancelExport()
  }, [cancelExport])

  const handleRetry = useCallback(() => {
    const currentFormat = format || 'pdf'
    reset()
    startExport(projectId, currentFormat)
  }, [reset, startExport, projectId, format])

  const handleDownload = useCallback(() => {
    download()
  }, [download])

  // Format display name
  const formatName = format === 'epub' ? 'EPUB' : 'PDF'

  // Determine what to render based on export phase
  const renderContent = () => {
    switch (state.phase) {
      case 'idle':
        return renderIdleState()
      case 'starting':
      case 'processing':
        return renderProgressState()
      case 'completed':
        return renderCompletedState()
      case 'failed':
        return renderFailedState()
      case 'cancelled':
        return renderCancelledState()
      default:
        return renderIdleState()
    }
  }

  const renderIdleState = () => (
    <div className="flex items-center justify-between">
      <div>
        <p className="text-slate-300">Export your ebook as PDF or EPUB.</p>
        <p className="text-sm text-slate-500 mt-1">
          Both formats include the cover page, table of contents, all chapters, and assigned
          images.
        </p>
      </div>
      <div className="flex gap-2">
        <button
          onClick={handleExportPdf}
          disabled={!canExport}
          className={`flex items-center gap-2 px-4 py-2 rounded-lg font-medium transition-colors ${
            canExport
              ? 'bg-cyan-500 text-white hover:bg-cyan-400'
              : 'bg-slate-700 text-slate-500 cursor-not-allowed'
          }`}
          title={canExport ? 'Download PDF' : disabledMessage || 'Export not available'}
        >
          <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
            />
          </svg>
          PDF
        </button>
        <button
          onClick={handleExportEpub}
          disabled={!canExport}
          className={`flex items-center gap-2 px-4 py-2 rounded-lg font-medium transition-colors ${
            canExport
              ? 'bg-emerald-500 text-white hover:bg-emerald-400'
              : 'bg-slate-700 text-slate-500 cursor-not-allowed'
          }`}
          title={canExport ? 'Download EPUB' : disabledMessage || 'Export not available'}
        >
          <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253"
            />
          </svg>
          EPUB
        </button>
      </div>
    </div>
  )

  const renderProgressState = () => (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-slate-300">
            {state.phase === 'starting' ? `Starting ${formatName} export...` : `Generating ${formatName}...`}
          </p>
          <p className="text-sm text-slate-500 mt-1">This may take a moment.</p>
        </div>
        <button
          onClick={handleCancel}
          className="flex items-center gap-2 px-4 py-2 rounded-lg font-medium bg-slate-700 text-slate-300 hover:bg-slate-600 transition-colors"
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M6 18L18 6M6 6l12 12"
            />
          </svg>
          Cancel
        </button>
      </div>

      {/* Progress bar */}
      <div className="w-full bg-slate-700 rounded-full h-2.5 overflow-hidden">
        <div
          className={`h-full rounded-full transition-all duration-300 ease-out ${
            format === 'epub' ? 'bg-emerald-500' : 'bg-cyan-500'
          }`}
          style={{ width: `${state.progress}%` }}
        />
      </div>
      <p className="text-sm text-slate-400 text-center">{state.progress}% complete</p>
    </div>
  )

  const renderCompletedState = () => (
    <div className="flex items-center justify-between">
      <div className="flex items-center gap-3">
        <div className="w-10 h-10 bg-green-500/20 rounded-full flex items-center justify-center">
          <svg
            className="w-5 h-5 text-green-400"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M5 13l4 4L19 7"
            />
          </svg>
        </div>
        <div>
          <p className="text-slate-300">{formatName} generated successfully!</p>
          <p className="text-sm text-slate-500">Your download should start automatically.</p>
        </div>
      </div>
      <div className="flex gap-2">
        <button
          onClick={handleDownload}
          className={`flex items-center gap-2 px-4 py-2 rounded-lg font-medium text-white transition-colors ${
            format === 'epub' ? 'bg-emerald-500 hover:bg-emerald-400' : 'bg-cyan-500 hover:bg-cyan-400'
          }`}
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"
            />
          </svg>
          Download Again
        </button>
        <button
          onClick={reset}
          className="flex items-center gap-2 px-4 py-2 rounded-lg font-medium bg-slate-700 text-slate-300 hover:bg-slate-600 transition-colors"
        >
          New Export
        </button>
      </div>
    </div>
  )

  const renderFailedState = () => (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <div className="w-10 h-10 bg-red-500/20 rounded-full flex items-center justify-center">
          <svg
            className="w-5 h-5 text-red-400"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
            />
          </svg>
        </div>
        <div>
          <p className="text-slate-300">{formatName} export failed</p>
          <p className="text-sm text-red-400">{state.error || 'An error occurred'}</p>
        </div>
      </div>
      <div className="flex gap-2">
        <button
          onClick={handleRetry}
          className={`flex items-center gap-2 px-4 py-2 rounded-lg font-medium text-white transition-colors ${
            format === 'epub' ? 'bg-emerald-500 hover:bg-emerald-400' : 'bg-cyan-500 hover:bg-cyan-400'
          }`}
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
            />
          </svg>
          Retry
        </button>
        <button
          onClick={reset}
          className="flex items-center gap-2 px-4 py-2 rounded-lg font-medium bg-slate-700 text-slate-300 hover:bg-slate-600 transition-colors"
        >
          Dismiss
        </button>
      </div>
    </div>
  )

  const renderCancelledState = () => (
    <div className="flex items-center justify-between">
      <div className="flex items-center gap-3">
        <div className="w-10 h-10 bg-yellow-500/20 rounded-full flex items-center justify-center">
          <svg
            className="w-5 h-5 text-yellow-400"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
            />
          </svg>
        </div>
        <div>
          <p className="text-slate-300">{formatName} export cancelled</p>
          <p className="text-sm text-slate-500">You can start a new export when ready.</p>
        </div>
      </div>
      <button
        onClick={reset}
        className="flex items-center gap-2 px-4 py-2 rounded-lg font-medium bg-cyan-500 text-white hover:bg-cyan-400 transition-colors"
      >
        Start New Export
      </button>
    </div>
  )

  return <div className="min-h-[100px]">{renderContent()}</div>
}
