/**
 * PreviewPanel Component
 *
 * Displays HTML preview of the assembled ebook in a sandboxed iframe.
 * Handles loading states, errors, and empty content gracefully.
 */

import { useState, useEffect, useCallback, useRef } from 'react'
import { getPreview } from '../../services/exportApi'
import { ApiException } from '../../services/api'

interface PreviewPanelProps {
  projectId: string
  /** Whether to include assigned images in preview */
  includeImages?: boolean
  /** Callback when preview content changes */
  onContentChange?: (hasContent: boolean) => void
  /** External trigger to refresh preview */
  refreshTrigger?: number
}

export function PreviewPanel({
  projectId,
  includeImages = true,
  onContentChange,
  refreshTrigger,
}: PreviewPanelProps) {
  const [html, setHtml] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const iframeRef = useRef<HTMLIFrameElement>(null)

  const loadPreview = useCallback(async () => {
    if (!projectId) return

    setIsLoading(true)
    setError(null)

    try {
      const result = await getPreview(projectId, includeImages)
      setHtml(result.html)
      onContentChange?.(!!result.html && !result.html.includes('No Draft Content'))
    } catch (err) {
      console.error('[PreviewPanel] Error loading preview:', err)
      if (err instanceof ApiException) {
        setError(err.message)
      } else {
        setError('Failed to load preview. Please try again.')
      }
      onContentChange?.(false)
    } finally {
      setIsLoading(false)
    }
  }, [projectId, includeImages, onContentChange])

  // Load preview on mount and when dependencies change
  useEffect(() => {
    loadPreview()
  }, [loadPreview, refreshTrigger])

  // Update iframe content when html changes
  useEffect(() => {
    if (iframeRef.current && html) {
      const iframe = iframeRef.current
      const doc = iframe.contentDocument || iframe.contentWindow?.document
      if (doc) {
        doc.open()
        doc.write(html)
        doc.close()
      }
    }
  }, [html])

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-96 bg-slate-900/50 rounded-lg border border-slate-700">
        <div className="text-center">
          <div className="inline-block animate-spin rounded-full h-8 w-8 border-4 border-slate-600 border-t-cyan-500 mb-3" />
          <p className="text-slate-400 text-sm">Loading preview...</p>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center h-96 bg-red-900/20 rounded-lg border border-red-500/30 p-6">
        <svg
          className="w-12 h-12 text-red-400 mb-3"
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
        <p className="text-red-400 text-center mb-4">{error}</p>
        <button
          onClick={loadPreview}
          className="px-4 py-2 bg-red-500/20 text-red-400 rounded-lg hover:bg-red-500/30 transition-colors text-sm"
        >
          Retry
        </button>
      </div>
    )
  }

  return (
    <div className="relative h-[600px] bg-white rounded-lg overflow-hidden shadow-lg">
      {/* Sandboxed iframe for rendering HTML */}
      <iframe
        ref={iframeRef}
        title="Ebook Preview"
        className="w-full h-full border-0"
        sandbox="allow-same-origin"
        style={{ background: 'white' }}
      />

      {/* Refresh button overlay */}
      <button
        onClick={loadPreview}
        className="absolute top-2 right-2 p-2 bg-slate-800/80 hover:bg-slate-700 rounded-lg text-slate-300 hover:text-white transition-colors shadow-lg"
        title="Refresh preview"
      >
        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
          />
        </svg>
      </button>
    </div>
  )
}
