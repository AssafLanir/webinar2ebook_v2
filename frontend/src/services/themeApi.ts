/**
 * Theme Proposal API client.
 *
 * Handles async theme proposal jobs for Ideas Edition.
 */

import type { Theme } from '../types/edition'
import { ApiException } from './api'

const API_BASE = 'http://localhost:8000'

// Response types
interface ApiResponse<T> {
  data: T | null
  error: { code: string; message: string } | null
}

interface ProposeThemesData {
  job_id: string
  status: string
}

interface ThemeStatusData {
  job_id: string
  status: 'queued' | 'processing' | 'completed' | 'failed' | 'cancelled'
  themes: Theme[]
  error: string | null
}

/**
 * Start a theme proposal job.
 */
export async function proposeThemes(projectId: string): Promise<ProposeThemesData> {
  const response = await fetch(`${API_BASE}/api/ai/themes/propose`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ project_id: projectId }),
  })

  const json: ApiResponse<ProposeThemesData> = await response.json()

  if (json.error) {
    throw new ApiException(json.error.code, json.error.message)
  }

  return json.data as ProposeThemesData
}

/**
 * Get the status of a theme proposal job.
 */
export async function getThemeStatus(jobId: string): Promise<ThemeStatusData> {
  const response = await fetch(`${API_BASE}/api/ai/themes/status/${jobId}`)

  const json: ApiResponse<ThemeStatusData> = await response.json()

  if (json.error) {
    throw new ApiException(json.error.code, json.error.message)
  }

  return json.data as ThemeStatusData
}

/**
 * Cancel a theme proposal job.
 */
export async function cancelThemeJob(jobId: string): Promise<{ job_id: string; cancelled: boolean }> {
  const response = await fetch(`${API_BASE}/api/ai/themes/cancel/${jobId}`, {
    method: 'POST',
  })

  const json: ApiResponse<{ job_id: string; cancelled: boolean }> = await response.json()

  if (json.error) {
    throw new ApiException(json.error.code, json.error.message)
  }

  return json.data as { job_id: string; cancelled: boolean }
}

/**
 * Poll a theme proposal job until completion.
 *
 * @param projectId - The project ID to propose themes for
 * @param onProgress - Optional callback for status updates
 * @returns The proposed themes
 */
export async function pollThemeProposal(
  projectId: string,
  onProgress?: (status: string) => void
): Promise<Theme[]> {
  const { job_id } = await proposeThemes(projectId)

  // Poll until complete
  while (true) {
    await new Promise((resolve) => setTimeout(resolve, 1000))

    const status = await getThemeStatus(job_id)

    onProgress?.(status.status)

    if (status.status === 'completed') {
      return status.themes
    }

    if (status.status === 'failed') {
      throw new Error(status.error || 'Theme proposal failed')
    }

    if (status.status === 'cancelled') {
      throw new Error('Theme proposal cancelled')
    }
  }
}
