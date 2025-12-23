/**
 * useExport Hook
 *
 * Manages the PDF export workflow:
 * - Starting export jobs
 * - Polling for progress
 * - Handling completion and download
 * - Cancellation
 *
 * Uses exportApi for backend communication.
 */

import { useState, useCallback, useRef, useEffect } from 'react'
import type { ExportState, ExportStatusData } from '../types/export'
import { initialExportState } from '../types/export'
import {
  startExport as apiStartExport,
  getExportStatus,
  cancelExport as apiCancelExport,
  downloadExport,
} from '../services/exportApi'
import { ApiException } from '../services/api'

const POLL_INTERVAL_MS = 1000

interface UseExportResult {
  /** Current export state */
  state: ExportState
  /** Start PDF export for a project */
  startExport: (projectId: string) => Promise<void>
  /** Cancel the current export */
  cancelExport: () => Promise<void>
  /** Trigger download for a completed export */
  download: () => Promise<void>
  /** Reset state to idle */
  reset: () => void
  /** Whether an export is currently in progress */
  isExporting: boolean
}

export function useExport(): UseExportResult {
  const [state, setState] = useState<ExportState>(initialExportState)
  const abortControllerRef = useRef<AbortController | null>(null)
  const projectIdRef = useRef<string | null>(null)
  const pollingRef = useRef<boolean>(false)

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      pollingRef.current = false
      abortControllerRef.current?.abort()
    }
  }, [])

  const startExport = useCallback(async (projectId: string) => {
    // Cancel any existing export
    if (abortControllerRef.current) {
      abortControllerRef.current.abort()
    }

    projectIdRef.current = projectId
    abortControllerRef.current = new AbortController()

    setState({
      phase: 'starting',
      jobId: null,
      progress: 0,
      downloadUrl: null,
      error: null,
    })

    try {
      // Start the export job
      const result = await apiStartExport(projectId)
      const jobId = result.job_id

      setState({
        phase: 'processing',
        jobId,
        progress: 0,
        downloadUrl: null,
        error: null,
      })

      // Start polling for status
      pollingRef.current = true
      await pollForCompletion(projectId, jobId)
    } catch (err) {
      console.error('[useExport] Start export failed:', err)
      const errorMessage = err instanceof ApiException ? err.message : 'Failed to start export'
      setState(prev => ({
        ...prev,
        phase: 'failed',
        error: errorMessage,
      }))
    }
  }, [])

  const pollForCompletion = async (projectId: string, jobId: string) => {
    while (pollingRef.current) {
      try {
        const status = await getExportStatus(projectId, jobId)

        // Update state based on status
        setState(prev => ({
          ...prev,
          progress: status.progress,
          downloadUrl: status.download_url,
        }))

        // Check for terminal states
        if (status.status === 'completed') {
          setState(prev => ({
            ...prev,
            phase: 'completed',
            progress: 100,
            downloadUrl: status.download_url,
          }))
          pollingRef.current = false

          // Auto-download on completion
          if (status.download_url) {
            await triggerDownload(projectId, jobId)
          }
          return
        }

        if (status.status === 'failed') {
          setState(prev => ({
            ...prev,
            phase: 'failed',
            error: status.error_message || 'Export failed',
          }))
          pollingRef.current = false
          return
        }

        if (status.status === 'cancelled') {
          setState(prev => ({
            ...prev,
            phase: 'cancelled',
          }))
          pollingRef.current = false
          return
        }

        // Wait before next poll
        await new Promise(resolve => setTimeout(resolve, POLL_INTERVAL_MS))
      } catch (err) {
        console.error('[useExport] Polling error:', err)
        if (!pollingRef.current) return // Aborted

        const errorMessage = err instanceof ApiException ? err.message : 'Failed to check export status'
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

  const triggerDownload = async (projectId: string, jobId: string) => {
    try {
      await downloadExport(projectId, jobId)
    } catch (err) {
      console.error('[useExport] Download failed:', err)
      // Don't fail the export state - it completed successfully, just download failed
      // User can retry via the download button
    }
  }

  const cancelExport = useCallback(async () => {
    const projectId = projectIdRef.current
    const jobId = state.jobId

    if (!projectId || !jobId) {
      return
    }

    // Stop polling
    pollingRef.current = false

    try {
      await apiCancelExport(projectId, jobId)
      setState(prev => ({
        ...prev,
        phase: 'cancelled',
      }))
    } catch (err) {
      console.error('[useExport] Cancel failed:', err)
      // Still stop polling even if cancel request failed
      setState(prev => ({
        ...prev,
        phase: 'cancelled',
      }))
    }
  }, [state.jobId])

  const download = useCallback(async () => {
    const projectId = projectIdRef.current
    const jobId = state.jobId

    if (!projectId || !jobId || state.phase !== 'completed') {
      return
    }

    try {
      await downloadExport(projectId, jobId)
    } catch (err) {
      console.error('[useExport] Download failed:', err)
      const errorMessage = err instanceof ApiException ? err.message : 'Download failed'
      setState(prev => ({
        ...prev,
        error: errorMessage,
      }))
    }
  }, [state.jobId, state.phase])

  const reset = useCallback(() => {
    pollingRef.current = false
    abortControllerRef.current?.abort()
    projectIdRef.current = null
    setState(initialExportState)
  }, [])

  const isExporting = state.phase === 'starting' || state.phase === 'processing'

  return {
    state,
    startExport,
    cancelExport,
    download,
    reset,
    isExporting,
  }
}
