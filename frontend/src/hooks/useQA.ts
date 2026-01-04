/**
 * useQA Hook
 *
 * T023: Manages the QA workflow:
 * - Loading existing QA reports
 * - Starting new QA analysis
 * - Polling for progress
 * - Handling completion and errors
 * - Cancellation
 *
 * Uses qaApi for backend communication.
 */

import { useState, useCallback, useRef, useEffect } from 'react'
import type { QAState } from '../types/qa'
import { initialQAState } from '../types/qa'
import {
  startQAAnalysis,
  getQAStatus,
  getQAReport,
  cancelQAAnalysis,
} from '../services/qaApi'
import { ApiException } from '../services/api'

const POLL_INTERVAL_MS = 2000

interface UseQAResult {
  /** Current QA state */
  state: QAState
  /** Load existing QA report for a project */
  loadReport: (projectId: string) => Promise<void>
  /** Start QA analysis for a project */
  startAnalysis: (projectId: string, force?: boolean) => Promise<void>
  /** Cancel the current analysis */
  cancelAnalysis: () => Promise<void>
  /** Reset state to idle */
  reset: () => void
  /** Toggle expanded state */
  toggleExpanded: () => void
  /** Whether analysis is currently running */
  isAnalyzing: boolean
  /** Whether we have a report available */
  hasReport: boolean
}

export function useQA(): UseQAResult {
  const [state, setState] = useState<QAState>(initialQAState)
  const pollingRef = useRef<boolean>(false)
  const projectIdRef = useRef<string | null>(null)

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      pollingRef.current = false
    }
  }, [])

  // Poll for analysis completion
  const pollForCompletion = async (_projectId: string, jobId: string) => {
    while (pollingRef.current) {
      try {
        const status = await getQAStatus(jobId)

        // Update progress
        setState(prev => ({
          ...prev,
          progress: status.progress_pct,
        }))

        // Check for terminal states
        if (status.status === 'completed' && status.report) {
          setState(prev => ({
            ...prev,
            phase: 'completed',
            progress: 100,
            report: status.report,
            error: null,
          }))
          pollingRef.current = false
          return
        }

        if (status.status === 'failed') {
          setState(prev => ({
            ...prev,
            phase: 'failed',
            error: status.error || 'Analysis failed',
          }))
          pollingRef.current = false
          return
        }

        if (status.status === 'cancelled') {
          setState(prev => ({
            ...prev,
            phase: 'idle',
            error: null,
          }))
          pollingRef.current = false
          return
        }

        // Wait before next poll
        await new Promise(resolve => setTimeout(resolve, POLL_INTERVAL_MS))
      } catch (err) {
        console.error('[useQA] Polling error:', err)
        if (!pollingRef.current) return // Aborted

        const errorMessage = err instanceof ApiException ? err.message : 'Failed to check analysis status'
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

  const loadReport = useCallback(async (projectId: string) => {
    projectIdRef.current = projectId

    try {
      const report = await getQAReport(projectId)

      if (report) {
        setState(prev => ({
          ...prev,
          phase: 'completed',
          report,
          error: null,
        }))
      } else {
        // No report yet
        setState(prev => ({
          ...prev,
          phase: 'idle',
          report: null,
        }))
      }
    } catch (err) {
      console.error('[useQA] Load report failed:', err)
      // Don't fail state, just log - report may not exist yet
    }
  }, [])

  const startAnalysis = useCallback(async (projectId: string, force: boolean = false) => {
    projectIdRef.current = projectId
    pollingRef.current = false // Stop any existing polling

    setState({
      ...initialQAState,
      phase: 'analyzing',
      progress: 0,
    })

    try {
      const result = await startQAAnalysis(projectId, force)

      // Check if already current (no job_id returned)
      if (!result.job_id) {
        // Already up to date, load existing report
        await loadReport(projectId)
        return
      }

      setState(prev => ({
        ...prev,
        jobId: result.job_id,
      }))

      // Start polling
      pollingRef.current = true
      await pollForCompletion(projectId, result.job_id)
    } catch (err) {
      console.error('[useQA] Start analysis failed:', err)
      const errorMessage = err instanceof ApiException ? err.message : 'Failed to start analysis'
      setState(prev => ({
        ...prev,
        phase: 'failed',
        error: errorMessage,
      }))
    }
  }, [loadReport])

  const cancelAnalysis = useCallback(async () => {
    const jobId = state.jobId

    if (!jobId) {
      return
    }

    // Stop polling
    pollingRef.current = false

    try {
      await cancelQAAnalysis(jobId)
      setState(prev => ({
        ...prev,
        phase: 'idle',
        error: null,
      }))
    } catch (err) {
      console.error('[useQA] Cancel failed:', err)
      // Still stop polling even if cancel request failed
      setState(prev => ({
        ...prev,
        phase: 'idle',
      }))
    }
  }, [state.jobId])

  const reset = useCallback(() => {
    pollingRef.current = false
    projectIdRef.current = null
    setState(initialQAState)
  }, [])

  const toggleExpanded = useCallback(() => {
    setState(prev => ({
      ...prev,
      isExpanded: !prev.isExpanded,
    }))
  }, [])

  const isAnalyzing = state.phase === 'analyzing'
  const hasReport = state.report !== null

  return {
    state,
    loadReport,
    startAnalysis,
    cancelAnalysis,
    reset,
    toggleExpanded,
    isAnalyzing,
    hasReport,
  }
}
