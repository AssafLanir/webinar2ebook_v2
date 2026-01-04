/**
 * RewriteDiffView Component (Spec 009 US3)
 *
 * T050: Displays before/after diffs from rewrite operations.
 * Shows each rewritten section with:
 * - Heading
 * - Original text
 * - Rewritten text
 * - Changes summary
 */

import { useState } from 'react'
import type { SectionDiff } from '../../types/qa'

interface RewriteDiffViewProps {
  diffs: SectionDiff[]
  onClose?: () => void
}

function DiffSection({ diff }: { diff: SectionDiff }) {
  const [showOriginal, setShowOriginal] = useState(true)

  return (
    <div className="border border-slate-700 rounded-lg overflow-hidden">
      {/* Header */}
      <div className="px-4 py-2 bg-slate-700/50 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="font-medium text-slate-200">
            {diff.heading || 'Untitled Section'}
          </span>
          <span className="text-xs text-slate-500">{diff.changes_summary}</span>
        </div>
        <div className="flex gap-1">
          <button
            onClick={() => setShowOriginal(true)}
            className={`px-2 py-1 text-xs rounded ${
              showOriginal
                ? 'bg-red-500/20 text-red-400'
                : 'bg-slate-600 text-slate-400 hover:text-slate-200'
            }`}
          >
            Original
          </button>
          <button
            onClick={() => setShowOriginal(false)}
            className={`px-2 py-1 text-xs rounded ${
              !showOriginal
                ? 'bg-green-500/20 text-green-400'
                : 'bg-slate-600 text-slate-400 hover:text-slate-200'
            }`}
          >
            Rewritten
          </button>
        </div>
      </div>

      {/* Content */}
      <div className="p-4 bg-slate-800/50">
        {showOriginal ? (
          <div className="text-sm text-slate-400 whitespace-pre-wrap font-mono">
            {diff.original}
          </div>
        ) : (
          <div className="text-sm text-slate-200 whitespace-pre-wrap font-mono">
            {diff.rewritten}
          </div>
        )}
      </div>
    </div>
  )
}

export function RewriteDiffView({ diffs, onClose }: RewriteDiffViewProps) {
  if (diffs.length === 0) {
    return (
      <div className="text-center py-8 text-slate-400">
        No sections were rewritten.
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-medium text-slate-200">
          Rewrite Results ({diffs.length} section{diffs.length !== 1 ? 's' : ''})
        </h3>
        {onClose && (
          <button
            onClick={onClose}
            className="p-1 text-slate-400 hover:text-slate-200 transition-colors"
          >
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        )}
      </div>

      {/* Diff list */}
      <div className="space-y-3">
        {diffs.map(diff => (
          <DiffSection key={diff.section_id} diff={diff} />
        ))}
      </div>

      {/* Legend */}
      <div className="flex items-center gap-4 text-xs text-slate-500 pt-2 border-t border-slate-700">
        <div className="flex items-center gap-1">
          <span className="w-3 h-3 rounded bg-red-500/20 border border-red-500/50" />
          <span>Original text</span>
        </div>
        <div className="flex items-center gap-1">
          <span className="w-3 h-3 rounded bg-green-500/20 border border-green-500/50" />
          <span>Rewritten text</span>
        </div>
      </div>
    </div>
  )
}
