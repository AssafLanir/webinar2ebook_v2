/**
 * Draft Generation API Client
 *
 * Provides functions for interacting with draft generation endpoints:
 * - Start generation (returns job ID for polling)
 * - Get status (poll for progress and results)
 * - Cancel generation
 * - Regenerate section
 */

import type {
  DraftGenerateRequest,
  DraftGenerateData,
  DraftStatusData,
  DraftCancelData,
  DraftRegenerateRequest,
  DraftRegenerateData,
} from '../types/draft'
import { ApiException } from './api'

const API_BASE = 'http://localhost:8000/api/ai/draft'

// Response envelope type
interface ApiResponse<T> {
  data: T | null
  error: { code: string; message: string } | null
}

/**
 * Make an API request and handle the response envelope.
 */
async function draftApiRequest<T>(
  path: string,
  options?: RequestInit
): Promise<T> {
  let response: Response

  try {
    response = await fetch(`${API_BASE}${path}`, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...options?.headers,
      },
    })
  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : 'Unknown error'

    if (errorMessage.includes('Failed to fetch') || errorMessage.includes('NetworkError')) {
      throw new ApiException(
        'NETWORK_ERROR',
        'Cannot connect to server. Please ensure the backend is running on http://localhost:8000'
      )
    }

    throw new ApiException(
      'NETWORK_ERROR',
      'Network error occurred. Please check your connection and try again.'
    )
  }

  if (response.status >= 500) {
    throw new ApiException(
      'SERVER_ERROR',
      'Server error occurred. Please try again later.'
    )
  }

  let json: ApiResponse<T>
  try {
    json = await response.json()
  } catch {
    if (response.status === 502 || response.status === 503 || response.status === 504) {
      throw new ApiException(
        'SERVICE_UNAVAILABLE',
        'Draft generation service is temporarily unavailable. Please try again later.'
      )
    }
    throw new ApiException(
      'INVALID_RESPONSE',
      `Server returned invalid response (status ${response.status})`
    )
  }

  if (json.error) {
    throw new ApiException(json.error.code, json.error.message)
  }

  return json.data as T
}

// ============================================================================
// Draft Generation API
// ============================================================================

/**
 * Start draft generation.
 *
 * Creates an async job and returns immediately with job ID.
 * Poll /status/{job_id} for progress updates.
 *
 * @param request - Generation request with transcript, outline, style config
 * @returns Job ID and initial status
 */
export async function startDraftGeneration(
  request: DraftGenerateRequest
): Promise<DraftGenerateData> {
  return draftApiRequest<DraftGenerateData>('/generate', {
    method: 'POST',
    body: JSON.stringify(request),
  })
}

/**
 * Get draft generation status.
 *
 * Poll this endpoint to track progress and get results.
 *
 * @param jobId - Job ID from startDraftGeneration
 * @returns Current status, progress info, and results when complete
 */
export async function getDraftStatus(jobId: string): Promise<DraftStatusData> {
  return draftApiRequest<DraftStatusData>(`/status/${jobId}`)
}

/**
 * Cancel draft generation.
 *
 * Cancellation is cooperative - the job will stop after the current
 * chapter completes. Partial results are preserved.
 *
 * @param jobId - Job ID to cancel
 * @returns Cancellation status and any partial results
 */
export async function cancelDraftGeneration(jobId: string): Promise<DraftCancelData> {
  return draftApiRequest<DraftCancelData>(`/cancel/${jobId}`, {
    method: 'POST',
  })
}

/**
 * Regenerate a single section/chapter.
 *
 * Synchronous operation - waits for regeneration to complete.
 *
 * @param request - Regeneration request with section ID and context
 * @returns New section markdown and position info
 */
export async function regenerateSection(
  request: DraftRegenerateRequest
): Promise<DraftRegenerateData> {
  return draftApiRequest<DraftRegenerateData>('/regenerate', {
    method: 'POST',
    body: JSON.stringify(request),
  })
}

// ============================================================================
// Polling Helper
// ============================================================================

/**
 * Poll for draft generation completion.
 *
 * Automatically polls the status endpoint until generation is complete,
 * cancelled, or failed. Calls the callback with each status update.
 *
 * @param jobId - Job ID to poll
 * @param onStatus - Callback for status updates
 * @param intervalMs - Polling interval (default 2000ms)
 * @returns Final status data
 */
export async function pollDraftGeneration(
  jobId: string,
  onStatus: (status: DraftStatusData) => void,
  intervalMs: number = 2000
): Promise<DraftStatusData> {
  const terminalStatuses = ['completed', 'cancelled', 'failed']

  while (true) {
    const status = await getDraftStatus(jobId)
    onStatus(status)

    if (terminalStatuses.includes(status.status)) {
      return status
    }

    await new Promise(resolve => setTimeout(resolve, intervalMs))
  }
}
