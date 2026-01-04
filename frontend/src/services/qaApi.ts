/**
 * QA (Quality Assessment) API Client
 *
 * T022: Provides functions for interacting with QA endpoints:
 * - Start analysis (returns job ID for polling)
 * - Get status (poll for progress and results)
 * - Get report (fetch existing report for a project)
 * - Cancel analysis
 */

import type {
  QAReport,
  QAJobStatus,
  RewriteStartData,
  RewriteStatusData,
  IssueType,
} from '../types/qa'
import { ApiException } from './api'

const API_BASE = 'http://localhost:8000/api/qa'

// Response envelope type
interface ApiResponse<T> {
  data: T | null
  error: { code: string; message: string } | null
}

// API Response types
interface QAAnalyzeResponse {
  job_id: string | null
  status: string
  message: string
}

interface QAStatusResponse {
  job_id: string
  status: QAJobStatus
  progress_pct: number
  current_stage: string | null
  report: QAReport | null
  error: string | null
}

interface QAReportResponse {
  report: QAReport | null
}

interface QACancelResponse {
  job_id: string
  status: string
  message: string
  cancelled: boolean
}

/**
 * Make an API request and handle the response envelope.
 */
async function qaApiRequest<T>(
  path: string,
  options?: RequestInit
): Promise<T> {
  let response: Response

  try {
    console.log(`[QA-API] ${options?.method ?? 'GET'} ${API_BASE}${path}`)
    response = await fetch(`${API_BASE}${path}`, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...options?.headers,
      },
    })
    console.log(`[QA-API] Response status: ${response.status}`)
  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : 'Unknown error'
    console.error(`[QA-API] Fetch error:`, error)

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
        'QA service is temporarily unavailable. Please try again later.'
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
// QA API Functions
// ============================================================================

/**
 * Start QA analysis for a project.
 *
 * Creates an async job and returns immediately with job ID.
 * Poll /status/{job_id} for progress updates.
 *
 * @param projectId - Project ID to analyze
 * @param force - Force reanalysis even if draft unchanged
 * @returns Job ID and initial status (null job_id if already current)
 */
export async function startQAAnalysis(
  projectId: string,
  force: boolean = false
): Promise<QAAnalyzeResponse> {
  return qaApiRequest<QAAnalyzeResponse>('/analyze', {
    method: 'POST',
    body: JSON.stringify({ project_id: projectId, force }),
  })
}

/**
 * Get QA job status.
 *
 * Poll this endpoint to track progress and get results.
 *
 * @param jobId - Job ID from startQAAnalysis
 * @returns Current status, progress info, and report when complete
 */
export async function getQAStatus(jobId: string): Promise<QAStatusResponse> {
  return qaApiRequest<QAStatusResponse>(`/status/${jobId}`)
}

/**
 * Get the latest QA report for a project.
 *
 * Returns the stored report without triggering new analysis.
 * Use startQAAnalysis to trigger new analysis.
 *
 * @param projectId - Project ID to get report for
 * @returns The QA report or null if none exists
 */
export async function getQAReport(projectId: string): Promise<QAReport | null> {
  const response = await qaApiRequest<QAReportResponse>(`/report/${projectId}`)
  return response.report
}

/**
 * Cancel an ongoing QA analysis.
 *
 * Cancellation is best-effort. The job may complete before cancellation
 * takes effect.
 *
 * @param jobId - Job ID to cancel
 * @returns Cancellation status
 */
export async function cancelQAAnalysis(jobId: string): Promise<QACancelResponse> {
  return qaApiRequest<QACancelResponse>(`/cancel/${jobId}`, {
    method: 'POST',
  })
}

// ============================================================================
// Polling Helper
// ============================================================================

/**
 * Poll for QA analysis completion.
 *
 * Automatically polls the status endpoint until analysis is complete
 * or failed. Calls the callback with each status update.
 *
 * @param jobId - Job ID to poll
 * @param onStatus - Callback for status updates
 * @param intervalMs - Polling interval (default 2000ms)
 * @returns Final status data
 */
export async function pollQAAnalysis(
  jobId: string,
  onStatus: (status: QAStatusResponse) => void,
  intervalMs: number = 2000
): Promise<QAStatusResponse> {
  const terminalStatuses: QAJobStatus[] = ['completed', 'failed', 'cancelled']

  while (true) {
    const status = await getQAStatus(jobId)
    onStatus(status)

    if (terminalStatuses.includes(status.status)) {
      return status
    }

    await new Promise(resolve => setTimeout(resolve, intervalMs))
  }
}

// ============================================================================
// Rewrite API Functions (Spec 009 US3)
// ============================================================================

/**
 * Start a targeted rewrite to fix QA issues.
 *
 * Creates an async job that rewrites sections flagged by QA
 * without adding new claims beyond the Evidence Map.
 *
 * @param projectId - Project ID to rewrite
 * @param issueTypes - Only fix these issue types (default: all)
 * @param passNumber - Which rewrite pass (1-3, default 1)
 * @returns Job ID and initial status
 */
export async function startRewrite(
  projectId: string,
  issueTypes?: IssueType[],
  passNumber: number = 1
): Promise<RewriteStartData> {
  return qaApiRequest<RewriteStartData>('/rewrite', {
    method: 'POST',
    body: JSON.stringify({
      project_id: projectId,
      issue_types: issueTypes,
      pass_number: passNumber,
    }),
  })
}

/**
 * Get rewrite job status.
 *
 * Poll this endpoint to track progress and get diffs.
 *
 * @param jobId - Job ID from startRewrite
 * @returns Current status, progress, and diffs when complete
 */
export async function getRewriteStatus(jobId: string): Promise<RewriteStatusData> {
  return qaApiRequest<RewriteStatusData>(`/rewrite/${jobId}`)
}
