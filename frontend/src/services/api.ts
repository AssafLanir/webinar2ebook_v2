/**
 * API client for backend communication.
 */

import type { Project, ProjectSummary, WebinarType } from '../types/project'

const API_BASE = 'http://localhost:8000'

// Error types
export interface ApiError {
  code: string
  message: string
}

export class ApiException extends Error {
  code: string

  constructor(code: string, message: string) {
    super(message)
    this.code = code
    this.name = 'ApiException'
  }
}

// Response envelope type
interface ApiResponse<T> {
  data: T | null
  error: ApiError | null
}

/**
 * Make an API request and handle the response envelope.
 */
async function apiRequest<T>(
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
    // Network error (server not running, CORS blocked, DNS failure, etc.)
    const errorMessage = error instanceof Error ? error.message : 'Unknown error'

    // Check for specific network error types
    if (errorMessage.includes('Failed to fetch') || errorMessage.includes('NetworkError')) {
      throw new ApiException(
        'NETWORK_ERROR',
        'Cannot connect to server. Please ensure the backend is running on http://localhost:8000'
      )
    }

    if (errorMessage.includes('CORS') || errorMessage.includes('blocked')) {
      throw new ApiException(
        'CORS_ERROR',
        'Request blocked by browser security. Check CORS configuration.'
      )
    }

    throw new ApiException(
      'NETWORK_ERROR',
      'Network error occurred. Please check your connection and try again.'
    )
  }

  // Handle HTTP error status codes before parsing JSON
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
    // Response wasn't JSON (might be HTML error page, etc.)
    if (response.status === 502 || response.status === 503 || response.status === 504) {
      throw new ApiException(
        'SERVICE_UNAVAILABLE',
        'Backend service is temporarily unavailable. Please try again later.'
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

// Project API functions

/**
 * Fetch all projects.
 */
export async function fetchProjects(): Promise<ProjectSummary[]> {
  return apiRequest<ProjectSummary[]>('/projects')
}

/**
 * Fetch a single project by ID.
 */
export async function fetchProject(id: string): Promise<Project> {
  return apiRequest<Project>(`/projects/${id}`)
}

/**
 * Create a new project.
 */
export async function createProject(
  name: string,
  webinarType: WebinarType
): Promise<Project> {
  return apiRequest<Project>('/projects', {
    method: 'POST',
    body: JSON.stringify({ name, webinarType }),
  })
}

/**
 * Update an existing project.
 */
export async function updateProject(
  id: string,
  project: Omit<Project, 'id' | 'createdAt' | 'updatedAt'>
): Promise<Project> {
  return apiRequest<Project>(`/projects/${id}`, {
    method: 'PUT',
    body: JSON.stringify(project),
  })
}

/**
 * Delete a project.
 */
export async function deleteProject(id: string): Promise<{ deleted: boolean }> {
  return apiRequest<{ deleted: boolean }>(`/projects/${id}`, {
    method: 'DELETE',
  })
}

/**
 * Health check.
 */
export async function healthCheck(): Promise<{ status: string }> {
  return apiRequest<{ status: string }>('/health')
}

// File API functions

/**
 * Upload response from the server.
 */
export interface UploadedResource {
  id: string
  label: string
  order: number
  resourceType: 'file'
  urlOrNote: string
  fileId: string
  fileName: string
  fileSize: number
  mimeType: string
  storagePath: string
}

/**
 * Upload a file to a project as a resource.
 * Uses multipart/form-data for file upload.
 */
export async function uploadFile(
  projectId: string,
  file: File,
  label?: string
): Promise<UploadedResource> {
  const formData = new FormData()
  formData.append('file', file)
  if (label) {
    formData.append('label', label)
  }

  let response: Response

  try {
    response = await fetch(`${API_BASE}/projects/${projectId}/files`, {
      method: 'POST',
      body: formData,
      // Note: Don't set Content-Type header - browser will set it with boundary
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
      'Network error occurred during file upload. Please check your connection and try again.'
    )
  }

  if (response.status >= 500) {
    throw new ApiException(
      'SERVER_ERROR',
      'Server error occurred during file upload. Please try again later.'
    )
  }

  let json: ApiResponse<UploadedResource>
  try {
    json = await response.json()
  } catch {
    throw new ApiException(
      'INVALID_RESPONSE',
      `Server returned invalid response (status ${response.status})`
    )
  }

  if (json.error) {
    throw new ApiException(json.error.code, json.error.message)
  }

  return json.data as UploadedResource
}

/**
 * Get the download URL for a file resource.
 * This returns a direct URL that can be used for downloading or linking.
 */
export function getFileDownloadUrl(projectId: string, fileId: string): string {
  return `${API_BASE}/projects/${projectId}/files/${fileId}`
}

/**
 * Delete a file from a project.
 */
export async function deleteFile(
  projectId: string,
  fileId: string
): Promise<{ deleted: boolean }> {
  return apiRequest<{ deleted: boolean }>(`/projects/${projectId}/files/${fileId}`, {
    method: 'DELETE',
  })
}
