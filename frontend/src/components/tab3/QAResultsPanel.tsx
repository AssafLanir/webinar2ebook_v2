/**
 * QAResultsPanel - Collapsible panel showing QA check results.
 *
 * Displays issues found in the draft with clickable items
 * that can scroll to the issue location in the editor.
 */

import { useState } from 'react'
import type { QAResult, QAIssue } from '../../utils/draftQA'
import { getIssueTypeLabel, getIssueTypeColor } from '../../utils/draftQA'

export interface QAResultsPanelProps {
  /** QA results to display */
  result: QAResult | null
  /** Whether QA is currently running */
  isRunning: boolean
  /** Callback when an issue is clicked (to scroll to it) */
  onIssueClick?: (issue: QAIssue) => void
  /** Callback to close/dismiss the panel */
  onClose: () => void
}

export function QAResultsPanel({
  result,
  isRunning,
  onIssueClick,
  onClose,
}: QAResultsPanelProps) {
  const [isExpanded, setIsExpanded] = useState(true)

  if (!result && !isRunning) {
    return null
  }

  const hasIssues = result && result.totalIssues > 0
  const noIssues = result && result.totalIssues === 0

  return (
    <div className="mt-4 bg-slate-800/50 rounded-xl border border-slate-700 overflow-hidden">
      {/* Header */}
      <div
        className="flex items-center justify-between px-4 py-3 cursor-pointer hover:bg-slate-700/30 transition-colors"
        onClick={() => setIsExpanded(!isExpanded)}
      >
        <div className="flex items-center gap-3">
          {isRunning ? (
            <>
              <svg className="w-5 h-5 animate-spin text-cyan-400" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
              </svg>
              <span className="text-slate-300 font-medium">Running QA checks...</span>
            </>
          ) : noIssues ? (
            <>
              <svg className="w-5 h-5 text-green-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <span className="text-green-400 font-medium">No issues found</span>
            </>
          ) : hasIssues ? (
            <>
              <svg className="w-5 h-5 text-yellow-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
              </svg>
              <span className="text-yellow-400 font-medium">
                {result.totalIssues} {result.totalIssues === 1 ? 'issue' : 'issues'} found
              </span>
            </>
          ) : null}
        </div>

        <div className="flex items-center gap-2">
          {/* Expand/Collapse button */}
          {hasIssues && (
            <button
              type="button"
              className="p-1 text-slate-400 hover:text-white transition-colors"
              onClick={(e) => {
                e.stopPropagation()
                setIsExpanded(!isExpanded)
              }}
            >
              <svg
                className={`w-5 h-5 transition-transform ${isExpanded ? 'rotate-180' : ''}`}
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
              </svg>
            </button>
          )}

          {/* Close button */}
          <button
            type="button"
            className="p-1 text-slate-400 hover:text-white transition-colors"
            onClick={(e) => {
              e.stopPropagation()
              onClose()
            }}
          >
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
      </div>

      {/* Issue List */}
      {hasIssues && isExpanded && (
        <div className="border-t border-slate-700">
          <div className="max-h-64 overflow-y-auto">
            {result.issues.map((issue, index) => (
              <IssueItem
                key={`${issue.type}-${issue.position}-${index}`}
                issue={issue}
                onClick={() => onIssueClick?.(issue)}
              />
            ))}
          </div>
        </div>
      )}

      {/* No issues message */}
      {noIssues && isExpanded && (
        <div className="border-t border-slate-700 px-4 py-3">
          <p className="text-sm text-slate-400">
            Your draft passed all quality checks. Great work!
          </p>
        </div>
      )}
    </div>
  )
}

interface IssueItemProps {
  issue: QAIssue
  onClick?: () => void
}

function IssueItem({ issue, onClick }: IssueItemProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="w-full px-4 py-3 text-left hover:bg-slate-700/30 transition-colors border-b border-slate-700/50 last:border-b-0"
    >
      <div className="flex items-start gap-3">
        {/* Issue type badge */}
        <span
          className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-slate-700 ${getIssueTypeColor(issue.type)}`}
        >
          {getIssueTypeLabel(issue.type)}
        </span>

        <div className="flex-1 min-w-0">
          {/* Issue message */}
          <p className="text-sm text-slate-200">{issue.message}</p>

          {/* Location and preview */}
          <div className="mt-1 flex items-center gap-2 text-xs text-slate-500">
            <span>{issue.location}</span>
            {issue.text && issue.type !== 'long-paragraph' && (
              <>
                <span>·</span>
                <code className="px-1 py-0.5 bg-slate-900 rounded text-slate-400 truncate max-w-[200px]">
                  {issue.text}
                </code>
              </>
            )}
          </div>
        </div>

        {/* Arrow indicator */}
        <svg className="w-4 h-4 text-slate-500 flex-shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
        </svg>
      </div>
    </button>
  )
}
