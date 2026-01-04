/**
 * QAIssueList Component
 *
 * T024: Displays a list of QA issues grouped by severity.
 * Handles truncation display when issues are capped.
 */

import type { QAIssue, IssueSeverity } from '../../types/qa'
import { getSeverityColor } from '../../types/qa'

interface QAIssueListProps {
  issues: QAIssue[]
  truncated: boolean
  totalCount: number
}

// Severity order for grouping
const SEVERITY_ORDER: IssueSeverity[] = ['critical', 'warning', 'info']

// Icons for each severity
function SeverityIcon({ severity }: { severity: IssueSeverity }) {
  switch (severity) {
    case 'critical':
      return (
        <svg className="w-4 h-4 text-red-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
      )
    case 'warning':
      return (
        <svg className="w-4 h-4 text-yellow-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
        </svg>
      )
    case 'info':
      return (
        <svg className="w-4 h-4 text-blue-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
      )
  }
}

function IssueItem({ issue }: { issue: QAIssue }) {
  return (
    <div className="py-2 px-3 bg-slate-800/50 rounded-lg">
      <div className="flex items-start gap-2">
        <SeverityIcon severity={issue.severity} />
        <div className="flex-1 min-w-0">
          <p className="text-sm text-slate-200">{issue.message}</p>
          {issue.heading && (
            <p className="text-xs text-slate-400 mt-1">
              Chapter: {issue.heading}
            </p>
          )}
          {issue.suggestion && (
            <p className="text-xs text-slate-500 mt-1 italic">
              {issue.suggestion}
            </p>
          )}
        </div>
      </div>
    </div>
  )
}

export function QAIssueList({ issues, truncated, totalCount }: QAIssueListProps) {
  // Group issues by severity
  const groupedIssues = SEVERITY_ORDER.reduce((acc, severity) => {
    acc[severity] = issues.filter(i => i.severity === severity)
    return acc
  }, {} as Record<IssueSeverity, QAIssue[]>)

  const severityLabels: Record<IssueSeverity, string> = {
    critical: 'Critical Issues',
    warning: 'Warnings',
    info: 'Suggestions',
  }

  return (
    <div className="space-y-4">
      {SEVERITY_ORDER.map(severity => {
        const severityIssues = groupedIssues[severity]
        if (severityIssues.length === 0) return null

        return (
          <div key={severity}>
            <h4 className={`text-sm font-medium mb-2 ${getSeverityColor(severity).split(' ')[0]}`}>
              {severityLabels[severity]} ({severityIssues.length})
            </h4>
            <div className="space-y-2">
              {severityIssues.map(issue => (
                <IssueItem key={issue.id} issue={issue} />
              ))}
            </div>
          </div>
        )
      })}

      {issues.length === 0 && (
        <p className="text-sm text-slate-400 text-center py-4">
          No issues found. Your draft looks good!
        </p>
      )}

      {truncated && (
        <p className="text-xs text-slate-500 text-center py-2 border-t border-slate-700">
          Showing {issues.length} of {totalCount} issues. Most critical issues are shown first.
        </p>
      )}
    </div>
  )
}
