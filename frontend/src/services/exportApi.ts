/**
 * Export API Client
 *
 * Provides functions for interacting with ebook preview and export endpoints:
 * - Get HTML preview
 * - Start PDF export (returns job ID for polling)
 * - Get export status (poll for progress)
 * - Download completed PDF
 * - Cancel export
 */

import type {
  ExportCancelData,
  ExportStartData,
  ExportStatusData,
  PreviewData,
} from '../types/export'
import { ApiException } from './api'

const API_BASE = 'http://localhost:8000/api/projects'

// Response envelope type
interface ApiResponse<T> {
  data: T | null
  error: { code: string; message: string } | null
}

/**
 * Make an API request and handle the response envelope.
 */
async function exportApiRequest<T>(
  path: string,
  options?: RequestInit
): Promise<T> {
  let response: Response

  try {
    console.log(`[ExportAPI] ${options?.method ?? 'GET'} ${path}`)
    response = await fetch(`${API_BASE}${path}`, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...options?.headers,
      },
    })
    console.log(`[ExportAPI] Response status: ${response.status}`)
  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : 'Unknown error'
    console.error(`[ExportAPI] Fetch error:`, error)

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
        'Export service is temporarily unavailable. Please try again later.'
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
// Preview API
// ============================================================================

/**
 * Get HTML preview of the assembled ebook.
 *
 * @param projectId - Project ID
 * @param includeImages - Whether to include assigned images (default true)
 * @returns Preview HTML content
 */
export async function getPreview(
  projectId: string,
  includeImages: boolean = true
): Promise<PreviewData> {
  const params = new URLSearchParams()
  if (!includeImages) {
    params.set('include_images', 'false')
  }
  const query = params.toString() ? `?${params.toString()}` : ''
  return exportApiRequest<PreviewData>(`/${projectId}/ebook/preview${query}`)
}

// ============================================================================
// Export API
// ============================================================================

/**
 * Start PDF or EPUB export.
 *
 * Creates an async job and returns immediately with job ID.
 * Poll /export/status/{job_id} for progress updates.
 *
 * @param projectId - Project ID
 * @param format - Export format: 'pdf' (default) or 'epub'
 * @returns Job ID and initial status
 */
export async function startExport(
  projectId: string,
  format: 'pdf' | 'epub' = 'pdf'
): Promise<ExportStartData> {
  return exportApiRequest<ExportStartData>(`/${projectId}/ebook/export?format=${format}`, {
    method: 'POST',
  })
}

/**
 * Get export status.
 *
 * Poll this endpoint to track progress.
 *
 * @param projectId - Project ID
 * @param jobId - Job ID from startExport
 * @returns Current status and progress info
 */
export async function getExportStatus(
  projectId: string,
  jobId: string
): Promise<ExportStatusData> {
  return exportApiRequest<ExportStatusData>(`/${projectId}/ebook/export/status/${jobId}`)
}

/**
 * Cancel export.
 *
 * @param projectId - Project ID
 * @param jobId - Job ID to cancel
 * @returns Cancellation status
 */
export async function cancelExport(
  projectId: string,
  jobId: string
): Promise<ExportCancelData> {
  return exportApiRequest<ExportCancelData>(`/${projectId}/ebook/export/cancel/${jobId}`, {
    method: 'POST',
  })
}

/**
 * Get the download URL for a completed export.
 *
 * @param projectId - Project ID
 * @param jobId - Completed job ID
 * @returns Direct download URL
 */
export function getExportDownloadUrl(projectId: string, jobId: string): string {
  return `${API_BASE}/${projectId}/ebook/export/download/${jobId}`
}

/**
 * Download a completed export.
 *
 * Triggers browser download of the PDF or EPUB file.
 *
 * @param projectId - Project ID
 * @param jobId - Completed job ID
 * @param filename - Suggested filename for download (auto-detected from response if not provided)
 */
export async function downloadExport(
  projectId: string,
  jobId: string,
  filename?: string
): Promise<void> {
  const url = getExportDownloadUrl(projectId, jobId)

  // Use fetch to get the file, then trigger download
  const response = await fetch(url)

  if (!response.ok) {
    throw new ApiException(
      'DOWNLOAD_FAILED',
      `Failed to download export: ${response.statusText}`
    )
  }

  // Detect filename from Content-Disposition header if not provided
  let downloadFilename = filename
  if (!downloadFilename) {
    const contentDisposition = response.headers.get('Content-Disposition')
    if (contentDisposition) {
      const match = contentDisposition.match(/filename="?([^"]+)"?/)
      if (match) {
        downloadFilename = match[1]
      }
    }
    // Fallback based on content type
    if (!downloadFilename) {
      const contentType = response.headers.get('Content-Type')
      downloadFilename = contentType?.includes('epub') ? 'ebook.epub' : 'ebook.pdf'
    }
  }

  const blob = await response.blob()
  const downloadUrl = window.URL.createObjectURL(blob)

  // Create and click a temporary link to trigger download
  const link = document.createElement('a')
  link.href = downloadUrl
  link.download = downloadFilename
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)

  // Clean up the object URL
  window.URL.revokeObjectURL(downloadUrl)
}

// ============================================================================
// Polling Helper
// ============================================================================

/**
 * Poll for export completion.
 *
 * Automatically polls the status endpoint until export is complete,
 * cancelled, or failed. Calls the callback with each status update.
 *
 * @param projectId - Project ID
 * @param jobId - Job ID to poll
 * @param onStatus - Callback for status updates
 * @param intervalMs - Polling interval (default 1000ms)
 * @returns Final status data
 */
export async function pollExport(
  projectId: string,
  jobId: string,
  onStatus: (status: ExportStatusData) => void,
  intervalMs: number = 1000
): Promise<ExportStatusData> {
  const terminalStatuses = ['completed', 'cancelled', 'failed']

  while (true) {
    const status = await getExportStatus(projectId, jobId)
    onStatus(status)

    if (terminalStatuses.includes(status.status)) {
      return status
    }

    await new Promise(resolve => setTimeout(resolve, intervalMs))
  }
}
