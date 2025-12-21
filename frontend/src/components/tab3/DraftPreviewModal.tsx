/**
 * DraftPreviewModal - Modal for previewing generated ebook draft.
 *
 * Shows:
 * - Generated markdown content (scrollable)
 * - Generation statistics (chapters, words, time)
 * - Copy to clipboard button
 * - Apply / Discard actions
 */

import { useState } from 'react'
import { Button } from '../common/Button'
import type { GenerationStats } from '../../types/draft'

export interface DraftPreviewModalProps {
  /** Whether the modal is open */
  isOpen: boolean
  /** The generated draft markdown */
  draftMarkdown: string
  /** Generation statistics (optional) */
  stats?: GenerationStats | null
  /** Handler for applying the draft */
  onApply: () => void
  /** Handler for applying and jumping to editor */
  onApplyAndEdit?: () => void
  /** Handler for discarding/closing */
  onDiscard: () => void
}

export function DraftPreviewModal({
  isOpen,
  draftMarkdown,
  stats,
  onApply,
  onApplyAndEdit,
  onDiscard,
}: DraftPreviewModalProps) {
  const [copied, setCopied] = useState(false)
  const [viewMode, setViewMode] = useState<'preview' | 'raw'>('preview')

  if (!isOpen) {
    return null
  }

  const handleCopyToClipboard = async () => {
    try {
      await navigator.clipboard.writeText(draftMarkdown)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch (err) {
      console.error('Failed to copy to clipboard:', err)
    }
  }

  const handleBackdropClick = (e: React.MouseEvent) => {
    if (e.target === e.currentTarget) {
      onDiscard()
    }
  }

  // Simple word count
  const wordCount = draftMarkdown.split(/\s+/).filter(Boolean).length

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm"
      onClick={handleBackdropClick}
    >
      <div className="bg-slate-800 rounded-xl shadow-2xl border border-slate-700 w-full max-w-4xl max-h-[90vh] flex flex-col mx-4">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-700">
          <div className="flex items-center gap-4">
            <h2 className="text-xl font-semibold text-white">
              Generated Draft
            </h2>
            {stats && (
              <div className="flex items-center gap-3 text-sm text-slate-400">
                <span>{stats.chapters_generated} chapters</span>
                <span className="text-slate-600">|</span>
                <span>{stats.total_words.toLocaleString()} words</span>
                <span className="text-slate-600">|</span>
                <span>{formatDuration(stats.generation_time_ms)}</span>
              </div>
            )}
          </div>
          <button
            onClick={onDiscard}
            className="text-slate-400 hover:text-white transition-colors"
            aria-label="Close"
          >
            <CloseIcon />
          </button>
        </div>

        {/* Toolbar */}
        <div className="flex items-center justify-between px-6 py-3 border-b border-slate-700/50">
          <div className="flex items-center gap-2">
            <button
              onClick={() => setViewMode('preview')}
              className={`px-3 py-1.5 text-sm rounded-lg transition-colors ${
                viewMode === 'preview'
                  ? 'bg-cyan-500/20 text-cyan-400'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-slate-700'
              }`}
            >
              Preview
            </button>
            <button
              onClick={() => setViewMode('raw')}
              className={`px-3 py-1.5 text-sm rounded-lg transition-colors ${
                viewMode === 'raw'
                  ? 'bg-cyan-500/20 text-cyan-400'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-slate-700'
              }`}
            >
              Raw Markdown
            </button>
          </div>
          <button
            onClick={handleCopyToClipboard}
            className="flex items-center gap-1.5 px-3 py-1.5 text-sm rounded-lg bg-slate-700 text-slate-300 hover:bg-slate-600 transition-colors"
          >
            {copied ? (
              <>
                <CheckIcon />
                Copied!
              </>
            ) : (
              <>
                <CopyIcon />
                Copy
              </>
            )}
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6">
          {viewMode === 'raw' ? (
            <RawMarkdownView markdown={draftMarkdown} />
          ) : (
            <MarkdownPreview markdown={draftMarkdown} />
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between px-6 py-4 border-t border-slate-700">
          <div className="text-sm text-slate-500">
            {wordCount.toLocaleString()} words
          </div>
          <div className="flex items-center gap-3">
            <Button variant="ghost" onClick={onDiscard}>
              Discard
            </Button>
            {onApplyAndEdit && (
              <Button variant="secondary" onClick={onApplyAndEdit}>
                Apply & Edit
              </Button>
            )}
            <Button variant="primary" onClick={onApply}>
              Apply to Project
            </Button>
          </div>
        </div>
      </div>
    </div>
  )
}

// Raw markdown view
function RawMarkdownView({ markdown }: { markdown: string }) {
  return (
    <div className="bg-slate-900 rounded-lg p-4">
      <pre className="whitespace-pre-wrap text-slate-200 text-sm font-mono leading-relaxed">
        {markdown}
      </pre>
    </div>
  )
}

// Simple markdown preview (renders basic markdown styling)
function MarkdownPreview({ markdown }: { markdown: string }) {
  // Simple markdown-to-HTML conversion for preview
  // In production, use a proper markdown library like marked or react-markdown
  const renderMarkdown = (md: string): string => {
    return md
      // Headers
      .replace(/^### (.+)$/gm, '<h3 class="text-lg font-semibold text-white mt-6 mb-2">$1</h3>')
      .replace(/^## (.+)$/gm, '<h2 class="text-xl font-semibold text-white mt-8 mb-3">$1</h2>')
      .replace(/^# (.+)$/gm, '<h1 class="text-2xl font-bold text-white mt-4 mb-4">$1</h1>')
      // Bold and italic
      .replace(/\*\*(.+?)\*\*/g, '<strong class="text-white font-semibold">$1</strong>')
      .replace(/\*(.+?)\*/g, '<em class="text-slate-300 italic">$1</em>')
      // Line breaks
      .replace(/\n\n/g, '</p><p class="text-slate-300 leading-relaxed mb-4">')
      .replace(/\n/g, '<br />')
  }

  return (
    <div
      className="prose prose-invert prose-slate max-w-none"
      dangerouslySetInnerHTML={{
        __html: `<p class="text-slate-300 leading-relaxed mb-4">${renderMarkdown(markdown)}</p>`,
      }}
    />
  )
}

// Format duration from milliseconds
function formatDuration(ms: number): string {
  const seconds = Math.floor(ms / 1000)
  if (seconds < 60) {
    return `${seconds}s`
  }
  const minutes = Math.floor(seconds / 60)
  const secs = seconds % 60
  return `${minutes}m ${secs}s`
}

// Icons
function CloseIcon() {
  return (
    <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
    </svg>
  )
}

function CopyIcon() {
  return (
    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
    </svg>
  )
}

function CheckIcon() {
  return (
    <svg className="w-4 h-4 text-green-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
    </svg>
  )
}
