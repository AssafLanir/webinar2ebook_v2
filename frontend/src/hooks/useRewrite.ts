/**
 * useRewrite Hook (Spec 009 US3)
 *
 * T052: Manages the targeted rewrite workflow:
 * - Starting a rewrite job
 * - Polling for progress
 * - Handling completion with diffs
 * - Multi-pass warning logic
 */

import { useState, useCallback, useRef, useEffect } from 'react'
import type { RewriteState, IssueType } from '../types/qa'
import { initialRewriteState } from '../types/qa'
import { startRewrite, getRewriteStatus } from '../services/qaApi'
import { ApiException } from '../services/api'

const POLL_INTERVAL_MS = 2000

interface UseRewriteResult {
  /** Current rewrite state */
  state: RewriteState
  /** Start a rewrite job */
  startRewriteJob: (
    projectId: string,
    issueTypes?: IssueType[],
    passNumber?: number
  ) => Promise<void>
  /** Reset state to idle */
  reset: () => void
  /** Whether rewrite is in progress */
  isRewriting: boolean
  /** Whether we have diffs to show */
  hasDiffs: boolean
}

export function useRewrite(): UseRewriteResult {
  const [state, setState] = useState<RewriteState>(initialRewriteState)
  const pollingRef = useRef<boolean>(false)

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      pollingRef.current = false
    }
  }, [])

  // Poll for rewrite completion
  const pollForCompletion = async (jobId: string) => {
    while (pollingRef.current) {
      try {
        const status = await getRewriteStatus(jobId)

        // Update progress
        setState(prev => ({
          ...prev,
          progress: status.progress_pct,
        }))

        // Check for terminal states
        if (status.status === 'completed') {
          setState(prev => ({
            ...prev,
            phase: 'completed',
            progress: 100,
            sectionsRewritten: status.sections_rewritten ?? 0,
            issuesAddressed: status.issues_addressed ?? 0,
            diffs: status.diffs ?? [],
            error: null,
          }))
          pollingRef.current = false
          return
        }

        if (status.status === 'failed') {
          setState(prev => ({
            ...prev,
            phase: 'failed',
            error: status.error ?? 'Rewrite failed',
          }))
          pollingRef.current = false
          return
        }

        // Wait before next poll
        await new Promise(resolve => setTimeout(resolve, POLL_INTERVAL_MS))
      } catch (err) {
        console.error('[useRewrite] Polling error:', err)
        if (!pollingRef.current) return // Aborted

        const errorMessage = err instanceof ApiException ? err.message : 'Failed to check rewrite status'
        setState(prev => ({
          ...prev,
          phase: 'failed',
          error: errorMessage,
        }))
        pollingRef.current = false
        return
      }
    }
  }

  const startRewriteJob = useCallback(async (
    projectId: string,
    issueTypes?: IssueType[],
    passNumber: number = 1
  ) => {
    pollingRef.current = false // Stop any existing polling

    setState({
      ...initialRewriteState,
      phase: 'running',
      progress: 0,
    })

    try {
      const result = await startRewrite(projectId, issueTypes, passNumber)

      setState(prev => ({
        ...prev,
        jobId: result.job_id,
        warning: result.warning,
      }))

      // Start polling
      pollingRef.current = true
      await pollForCompletion(result.job_id)
    } catch (err) {
      console.error('[useRewrite] Start failed:', err)
      const errorMessage = err instanceof ApiException ? err.message : 'Failed to start rewrite'
      setState(prev => ({
        ...prev,
        phase: 'failed',
        error: errorMessage,
      }))
    }
  }, [])

  const reset = useCallback(() => {
    pollingRef.current = false
    setState(initialRewriteState)
  }, [])

  const isRewriting = state.phase === 'running'
  const hasDiffs = state.diffs.length > 0

  return {
    state,
    startRewriteJob,
    reset,
    isRewriting,
    hasDiffs,
  }
}
