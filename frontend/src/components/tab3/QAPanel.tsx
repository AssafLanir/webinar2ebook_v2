/**
 * QAPanel Component
 *
 * T025: Displays QA results in a collapsible panel with:
 * - Summary badge showing score and issue count
 * - Expandable issue list grouped by severity
 * - Progress indicator during analysis
 * - Rerun button for manual analysis
 */

import { useEffect, useState } from 'react'
import { Card } from '../common/Card'
import { Button } from '../common/Button'
import { QAIssueList } from './QAIssueList'
// TODO: Phase 4 (US3) - Rewrite UI
// import { RewriteDiffView } from './RewriteDiffView'
import { useQA } from '../../hooks/useQA'
import { useRewrite } from '../../hooks/useRewrite'
import { getScoreColor, getScoreLabel } from '../../types/qa'

interface QAPanelProps {
  projectId: string
  hasDraft: boolean
}

function ScoreBadge({ score }: { score: number }) {
  const colorClass = getScoreColor(score)
  const label = getScoreLabel(score)

  return (
    <div className="flex items-center gap-3">
      <div className={`text-2xl font-bold ${colorClass}`}>
        {score}
      </div>
      <div className="text-sm text-slate-400">
        {label}
      </div>
    </div>
  )
}

function RubricBar({ label, score }: { label: string; score: number }) {
  const colorClass = getScoreColor(score)

  return (
    <div className="flex items-center gap-2">
      <span className="text-xs text-slate-400 w-24">{label}</span>
      <div className="flex-1 h-2 bg-slate-700 rounded-full overflow-hidden">
        <div
          className={`h-full ${score >= 70 ? 'bg-green-500' : score >= 50 ? 'bg-yellow-500' : 'bg-red-500'}`}
          style={{ width: `${score}%` }}
        />
      </div>
      <span className={`text-xs font-medium w-8 text-right ${colorClass}`}>
        {score}
      </span>
    </div>
  )
}

function IssueCountBadge({ count, severity }: { count: number; severity: 'critical' | 'warning' | 'info' }) {
  if (count === 0) return null

  const colors = {
    critical: 'bg-red-500/20 text-red-400',
    warning: 'bg-yellow-500/20 text-yellow-400',
    info: 'bg-blue-500/20 text-blue-400',
  }

  return (
    <span className={`px-2 py-0.5 rounded text-xs font-medium ${colors[severity]}`}>
      {count}
    </span>
  )
}

export function QAPanel({ projectId, hasDraft }: QAPanelProps) {
  const {
    state,
    loadReport,
    startAnalysis,
    cancelAnalysis,
    toggleExpanded,
    isAnalyzing,
    hasReport,
  } = useQA()

  // TODO: Phase 4 (US3) - Rewrite functionality
  const {
    state: rewriteState,
    startRewriteJob: _startRewriteJob,
    reset: _resetRewrite,
    isRewriting: _isRewriting,
    hasDiffs,
  } = useRewrite()

  const [_showDiffs, _setShowDiffs] = useState(false)

  // Load existing report when projectId changes
  useEffect(() => {
    if (projectId && hasDraft) {
      loadReport(projectId)
    }
  }, [projectId, hasDraft, loadReport])

  // TODO: Phase 4 (US3) - Show diffs when rewrite completes
  useEffect(() => {
    if (rewriteState.phase === 'completed' && hasDiffs) {
      _setShowDiffs(true)
    }
  }, [rewriteState.phase, hasDiffs])

  const handleRunAnalysis = () => {
    startAnalysis(projectId, true) // Force rerun
  }

  // TODO: Phase 4 (US3) - Add handleFixIssues and handleCloseDiffs handlers here

  // Don't show panel if no draft
  if (!hasDraft) {
    return null
  }

  const { phase, progress, error, report, isExpanded } = state

  return (
    <Card
      title={
        <div className="flex items-center gap-2">
          <span>Quality Assessment</span>
          {hasReport && report && (
            <div className="flex items-center gap-1.5">
              <IssueCountBadge count={report.issue_counts.critical} severity="critical" />
              <IssueCountBadge count={report.issue_counts.warning} severity="warning" />
              <IssueCountBadge count={report.issue_counts.info} severity="info" />
            </div>
          )}
        </div>
      }
      headerAction={
        <div className="flex items-center gap-2">
          {isAnalyzing ? (
            <Button
              variant="secondary"
              size="sm"
              onClick={cancelAnalysis}
            >
              Cancel
            </Button>
          ) : (
            <Button
              variant="secondary"
              size="sm"
              onClick={handleRunAnalysis}
              disabled={isAnalyzing}
            >
              <svg className="w-4 h-4 mr-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
              </svg>
              Rerun
            </Button>
          )}
          {hasReport && (
            <button
              onClick={toggleExpanded}
              className="p-1 text-slate-400 hover:text-slate-200 transition-colors"
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
        </div>
      }
    >
      {/* Analyzing State */}
      {isAnalyzing && (
        <div className="py-6">
          <div className="flex items-center justify-center gap-3 mb-4">
            <svg className="w-5 h-5 text-cyan-400 animate-spin" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
            </svg>
            <span className="text-slate-300">Analyzing draft quality...</span>
          </div>
          <div className="w-full h-2 bg-slate-700 rounded-full overflow-hidden">
            <div
              className="h-full bg-cyan-500 transition-all duration-300"
              style={{ width: `${progress}%` }}
            />
          </div>
          <p className="text-center text-xs text-slate-500 mt-2">{progress}%</p>
        </div>
      )}

      {/* Error State */}
      {phase === 'failed' && error && (
        <div className="py-4">
          <div className="flex items-center gap-2 text-red-400 mb-2">
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <span className="text-sm">Analysis failed</span>
          </div>
          <p className="text-xs text-slate-400">{error}</p>
        </div>
      )}

      {/* No Report Yet */}
      {phase === 'idle' && !hasReport && (
        <div className="py-6 text-center">
          <p className="text-slate-400 text-sm mb-3">
            No quality report yet. Run analysis to check your draft.
          </p>
          <Button variant="primary" size="sm" onClick={handleRunAnalysis}>
            Run Analysis
          </Button>
        </div>
      )}

      {/* Report Summary (Always visible when report exists) */}
      {hasReport && report && !isAnalyzing && (
        <div className="space-y-4">
          {/* Score and Summary */}
          <div className="flex items-center justify-between">
            <ScoreBadge score={report.overall_score} />
            <div className="text-sm text-slate-400">
              {report.total_issue_count} issues found
            </div>
          </div>

          {/* Rubric Scores */}
          <div className="space-y-2 pt-2 border-t border-slate-700">
            <RubricBar label="Structure" score={report.rubric_scores.structure} />
            <RubricBar label="Clarity" score={report.rubric_scores.clarity} />
            <RubricBar label="Faithfulness" score={report.rubric_scores.faithfulness} />
            <RubricBar label="Repetition" score={report.rubric_scores.repetition} />
            <RubricBar label="Completeness" score={report.rubric_scores.completeness} />
          </div>

          {/* Expanded Issue List */}
          {isExpanded && (
            <div className="pt-4 border-t border-slate-700">
              <QAIssueList
                issues={report.issues}
                truncated={report.truncated}
                totalCount={report.total_issue_count}
              />
            </div>
          )}

          {/* Analysis Time */}
          <p className="text-xs text-slate-500 pt-2 border-t border-slate-700">
            Analysis completed in {(report.analysis_duration_ms / 1000).toFixed(1)}s
          </p>
        </div>
      )}
    </Card>
  )
}
