/**
 * GenerateProgress - Shows draft generation progress with cancel option.
 *
 * Displays:
 * - Current phase indicator
 * - Progress bar (chapters completed / total)
 * - Current chapter being generated
 * - Estimated time remaining
 * - Cancel button
 * - Error state
 */

import { Button } from '../common/Button'
import type { DraftGenerationState } from '../../types/draft'

export interface GenerateProgressProps {
  /** Current generation state from useDraftGeneration hook */
  state: DraftGenerationState
  /** Whether cancellation is in progress */
  isCancelling?: boolean
  /** Handler for cancel button */
  onCancel: () => void
  /** Handler for retry after failure */
  onRetry?: () => void
  /** Handler for viewing partial results */
  onViewPartial?: () => void
}

const phaseLabels: Record<DraftGenerationState['phase'], string> = {
  idle: 'Ready',
  starting: 'Starting...',
  planning: 'Planning chapters...',
  evidence_map: 'Building evidence map...',
  generating: 'Generating content...',
  completed: 'Generation complete',
  cancelled: 'Generation cancelled',
  failed: 'Generation failed',
}

const phaseColors: Record<DraftGenerationState['phase'], string> = {
  idle: 'text-slate-400',
  starting: 'text-cyan-400',
  planning: 'text-cyan-400',
  evidence_map: 'text-cyan-400',
  generating: 'text-cyan-400',
  completed: 'text-green-400',
  cancelled: 'text-yellow-400',
  failed: 'text-red-400',
}

export function GenerateProgress({
  state,
  isCancelling = false,
  onCancel,
  onRetry,
  onViewPartial,
}: GenerateProgressProps) {
  const { phase, progress, error, draftMarkdown, evidenceMapSummary, constraintWarnings } = state
  const isInProgress = ['starting', 'planning', 'evidence_map', 'generating'].includes(phase)
  const hasPartialResults = draftMarkdown !== null

  // Calculate progress percentage - 100% when completed
  const progressPercent = phase === 'completed'
    ? 100
    : (progress && progress.total_chapters > 0
        ? Math.round((progress.chapters_completed / progress.total_chapters) * 100)
        : 0)

  // Format estimated time
  const formatTime = (seconds: number | null | undefined): string => {
    if (!seconds) return ''
    if (seconds < 60) return `~${seconds}s remaining`
    const minutes = Math.floor(seconds / 60)
    const secs = seconds % 60
    return `~${minutes}m ${secs}s remaining`
  }

  return (
    <div className="bg-slate-800/50 rounded-xl border border-slate-700 p-6">
      {/* Phase indicator */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          {isInProgress && <LoadingSpinner />}
          {phase === 'completed' && <SuccessIcon />}
          {phase === 'failed' && <ErrorIcon />}
          {phase === 'cancelled' && <CancelledIcon />}
          <span className={`text-lg font-medium ${phaseColors[phase]}`}>
            {phaseLabels[phase]}
          </span>
        </div>

        {/* Cancel button */}
        {isInProgress && (
          <Button
            variant="secondary"
            size="sm"
            onClick={onCancel}
            disabled={isCancelling}
          >
            {isCancelling ? 'Cancelling...' : 'Cancel'}
          </Button>
        )}
      </div>

      {/* Progress bar and details */}
      {progress && progress.total_chapters > 0 && (
        <div className="space-y-3">
          {/* Progress bar */}
          <div className="relative h-2 bg-slate-700 rounded-full overflow-hidden">
            <div
              className="absolute inset-y-0 left-0 bg-gradient-to-r from-cyan-500 to-blue-500 transition-all duration-500 ease-out"
              style={{ width: `${progressPercent}%` }}
            />
          </div>

          {/* Progress details */}
          <div className="flex items-center justify-between text-sm">
            <div className="flex items-center gap-4">
              <span className="text-slate-300">
                {phase === 'completed'
                  ? `${progress.total_chapters} of ${progress.total_chapters} chapters completed`
                  : `Chapter ${progress.chapters_completed} of ${progress.total_chapters}`}
              </span>
              {isInProgress && progress.current_chapter_title && (
                <span className="text-slate-500">
                  Writing: {progress.current_chapter_title}
                </span>
              )}
            </div>
            {isInProgress && (
              <span className="text-slate-500">
                {formatTime(progress.estimated_remaining_seconds)}
              </span>
            )}
          </div>
        </div>
      )}

      {/* Evidence Map summary (Spec 009) */}
      {evidenceMapSummary && (
        <div className="mt-4 p-3 bg-slate-700/50 rounded-lg">
          <div className="flex items-center justify-between text-sm">
            <span className="text-slate-300">
              Evidence Map: {evidenceMapSummary.total_claims} claims
            </span>
            <span className="text-slate-500">
              Mode: {evidenceMapSummary.content_mode}
              {evidenceMapSummary.strict_grounded && ' (strict)'}
            </span>
          </div>
        </div>
      )}

      {/* Constraint warnings (Spec 009) */}
      {constraintWarnings && constraintWarnings.length > 0 && (
        <div className="mt-4 p-3 bg-amber-500/10 border border-amber-500/30 rounded-lg">
          <p className="text-sm font-medium text-amber-400 mb-2">Content Warnings</p>
          <ul className="space-y-1">
            {constraintWarnings.map((warning, idx) => (
              <li key={idx} className="text-sm text-amber-300/80">
                {warning}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Error message */}
      {phase === 'failed' && error && (
        <div className="mt-4 p-3 bg-red-500/10 border border-red-500/30 rounded-lg">
          <p className="text-sm text-red-400">{error}</p>
          {onRetry && (
            <Button
              variant="secondary"
              size="sm"
              onClick={onRetry}
              className="mt-3"
            >
              Try Again
            </Button>
          )}
        </div>
      )}

      {/* Cancelled with partial results */}
      {phase === 'cancelled' && hasPartialResults && (
        <div className="mt-4 p-3 bg-yellow-500/10 border border-yellow-500/30 rounded-lg">
          <p className="text-sm text-yellow-400">
            Generation was cancelled. Partial results are available.
          </p>
          {onViewPartial && (
            <Button
              variant="secondary"
              size="sm"
              onClick={onViewPartial}
              className="mt-3"
            >
              View Partial Draft
            </Button>
          )}
        </div>
      )}
    </div>
  )
}

// Loading spinner
function LoadingSpinner() {
  return (
    <svg
      className="w-5 h-5 animate-spin text-cyan-400"
      xmlns="http://www.w3.org/2000/svg"
      fill="none"
      viewBox="0 0 24 24"
    >
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
        d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
      />
    </svg>
  )
}

// Success icon
function SuccessIcon() {
  return (
    <svg className="w-5 h-5 text-green-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
    </svg>
  )
}

// Error icon
function ErrorIcon() {
  return (
    <svg className="w-5 h-5 text-red-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
    </svg>
  )
}

// Cancelled icon
function CancelledIcon() {
  return (
    <svg className="w-5 h-5 text-yellow-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M18.364 18.364A9 9 0 005.636 5.636m12.728 12.728A9 9 0 015.636 5.636m12.728 12.728L5.636 5.636" />
    </svg>
  )
}
