/**
 * Hook for managing draft generation lifecycle.
 *
 * Handles:
 * - Starting generation
 * - Polling for progress with reasonable intervals
 * - Cancellation
 * - State management for UI
 */

import { useState, useCallback, useRef, useEffect } from 'react'
import {
  startDraftGeneration,
  getDraftStatus,
  cancelDraftGeneration,
} from '../services/draftApi'
import type {
  DraftGenerateRequest,
  DraftGenerationState,
  DraftGenerationPhase,
  JobStatus,
} from '../types/draft'
import { ApiException } from '../services/api'

// Polling configuration
const INITIAL_POLL_INTERVAL = 2000 // 2 seconds
const MAX_POLL_INTERVAL = 5000 // 5 seconds (backoff cap)
const POLL_BACKOFF_FACTOR = 1.2 // Increase interval by 20% each poll

/**
 * Map job status to generation phase for UI.
 */
function statusToPhase(status: JobStatus): DraftGenerationPhase {
  switch (status) {
    case 'queued':
      return 'starting'
    case 'planning':
      return 'planning'
    case 'generating':
      return 'generating'
    case 'completed':
      return 'completed'
    case 'cancelled':
      return 'cancelled'
    case 'failed':
      return 'failed'
    default:
      return 'idle'
  }
}

export interface UseDraftGenerationResult {
  /** Current generation state */
  state: DraftGenerationState
  /** Start a new generation */
  startGeneration: (request: DraftGenerateRequest) => Promise<void>
  /** Cancel the current generation */
  cancelGeneration: () => Promise<void>
  /** Reset state to idle */
  reset: () => void
  /** Whether generation is in progress */
  isGenerating: boolean
  /** Whether generation can be cancelled */
  canCancel: boolean
}

export function useDraftGeneration(): UseDraftGenerationResult {
  const [state, setState] = useState<DraftGenerationState>({
    phase: 'idle',
    jobId: null,
    progress: null,
    error: null,
    draftMarkdown: null,
    draftPlan: null,
    visualPlan: null,
    stats: null,
  })

  // State to trigger polling effect (refs don't cause re-renders)
  const [pollingJobId, setPollingJobId] = useState<string | null>(null)

  // Refs for cleanup and control
  const pollTimeoutRef = useRef<number | null>(null)
  const pollIntervalRef = useRef<number>(INITIAL_POLL_INTERVAL)
  const isCancelledRef = useRef<boolean>(false)

  /**
   * Stop polling - clears timeout and resets state.
   */
  const stopPolling = useCallback(() => {
    setPollingJobId(null)
    isCancelledRef.current = true
    if (pollTimeoutRef.current) {
      clearTimeout(pollTimeoutRef.current)
      pollTimeoutRef.current = null
    }
  }, [])

  // Polling effect - runs when pollingJobId changes
  useEffect(() => {
    if (!pollingJobId) {
      return
    }

    let mounted = true
    isCancelledRef.current = false
    pollIntervalRef.current = INITIAL_POLL_INTERVAL

    const poll = async () => {
      if (!mounted || isCancelledRef.current) {
        return
      }

      try {
        const status = await getDraftStatus(pollingJobId)

        if (!mounted || isCancelledRef.current) return

        // Update state with latest status
        setState(prev => ({
          ...prev,
          phase: statusToPhase(status.status),
          progress: status.progress ?? prev.progress,
          draftMarkdown: status.draft_markdown ?? status.partial_draft_markdown ?? prev.draftMarkdown,
          draftPlan: status.draft_plan ?? prev.draftPlan,
          visualPlan: status.visual_plan ?? prev.visualPlan,
          stats: status.generation_stats ?? prev.stats,
        }))

        // Check for terminal state
        const isTerminal = ['completed', 'cancelled', 'failed'].includes(status.status)

        if (isTerminal) {
          // If failed, set error from response or fallback to generic message
          if (status.status === 'failed') {
            const errorMessage = status.error_message || 'Generation failed. Please try again.'
            setState(prev => ({
              ...prev,
              error: errorMessage,
            }))
          }
          pollIntervalRef.current = INITIAL_POLL_INTERVAL
          return
        }

        // Schedule next poll with backoff
        pollIntervalRef.current = Math.min(
          pollIntervalRef.current * POLL_BACKOFF_FACTOR,
          MAX_POLL_INTERVAL
        )

        if (mounted && !isCancelledRef.current) {
          pollTimeoutRef.current = window.setTimeout(poll, pollIntervalRef.current)
        }

      } catch (error) {
        if (!mounted || isCancelledRef.current) return

        const message = error instanceof ApiException
          ? error.message
          : 'Failed to get generation status'

        setState(prev => ({
          ...prev,
          phase: 'failed',
          error: message,
        }))
      }
    }

    // Start first poll immediately
    poll()

    return () => {
      mounted = false
      if (pollTimeoutRef.current) {
        clearTimeout(pollTimeoutRef.current)
        pollTimeoutRef.current = null
      }
    }
  }, [pollingJobId])

  // Cleanup polling on unmount
  useEffect(() => {
    return () => {
      if (pollTimeoutRef.current) {
        clearTimeout(pollTimeoutRef.current)
      }
    }
  }, [])

  /**
   * Start a new draft generation.
   */
  const startGeneration = useCallback(async (request: DraftGenerateRequest) => {
    // Reset state
    isCancelledRef.current = false
    pollIntervalRef.current = INITIAL_POLL_INTERVAL

    setState({
      phase: 'starting',
      jobId: null,
      progress: null,
      error: null,
      draftMarkdown: null,
      draftPlan: null,
      visualPlan: null,
      stats: null,
    })

    try {
      const result = await startDraftGeneration(request)

      setState(prev => ({
        ...prev,
        jobId: result.job_id,
        phase: statusToPhase(result.status),
      }))

      // Start polling - this triggers the useEffect
      setPollingJobId(result.job_id)

    } catch (error) {
      const message = error instanceof ApiException
        ? error.message
        : 'Failed to start generation'

      setState(prev => ({
        ...prev,
        phase: 'failed',
        error: message,
      }))
    }
  }, [])

  /**
   * Cancel the current generation.
   */
  const cancelGeneration = useCallback(async () => {
    if (!state.jobId) return

    isCancelledRef.current = true
    stopPolling()

    try {
      const result = await cancelDraftGeneration(state.jobId)

      setState(prev => ({
        ...prev,
        phase: 'cancelled',
        draftMarkdown: result.partial_draft_markdown ?? prev.draftMarkdown,
      }))

    } catch (error) {
      const message = error instanceof ApiException
        ? error.message
        : 'Failed to cancel generation'

      setState(prev => ({
        ...prev,
        error: message,
      }))
    }
  }, [state.jobId, stopPolling])

  /**
   * Reset state to idle.
   */
  const reset = useCallback(() => {
    isCancelledRef.current = true
    stopPolling()

    setState({
      phase: 'idle',
      jobId: null,
      progress: null,
      error: null,
      draftMarkdown: null,
      draftPlan: null,
      visualPlan: null,
      stats: null,
    })
  }, [stopPolling])

  // Computed properties
  const isGenerating = ['starting', 'planning', 'generating'].includes(state.phase)
  const canCancel = isGenerating && state.jobId !== null

  return {
    state,
    startGeneration,
    cancelGeneration,
    reset,
    isGenerating,
    canCancel,
  }
}
