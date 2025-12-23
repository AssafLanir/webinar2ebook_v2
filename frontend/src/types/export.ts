/**
 * Export Types (Spec 006)
 *
 * Types for Tab 4 Final Assembly + Preview + PDF Export.
 * Matches backend models from backend/src/models/export_job.py and api_responses.py
 */

// ============================================================================
// Export Format and Job Status
// ============================================================================

export type ExportFormat = 'pdf'
// Future: | 'epub' | 'docx'

export type ExportJobStatus = 'pending' | 'processing' | 'completed' | 'failed' | 'cancelled'

// ============================================================================
// API Request Types
// ============================================================================

export interface ExportStartRequest {
  format: ExportFormat
}

// ============================================================================
// API Response Data Types
// ============================================================================

export interface PreviewData {
  html: string
}

export interface ExportStartData {
  job_id: string
}

export interface ExportStatusData {
  job_id: string
  status: ExportJobStatus
  progress: number
  download_url: string | null
  error_message: string | null
}

export interface ExportCancelData {
  cancelled: boolean
}

// ============================================================================
// API Response Envelope Types
// ============================================================================

export interface ErrorDetail {
  code: string
  message: string
}

export interface PreviewResponse {
  data: PreviewData | null
  error: ErrorDetail | null
}

export interface ExportStartResponse {
  data: ExportStartData | null
  error: ErrorDetail | null
}

export interface ExportStatusResponse {
  data: ExportStatusData | null
  error: ErrorDetail | null
}

export interface ExportCancelResponse {
  data: ExportCancelData | null
  error: ErrorDetail | null
}

// ============================================================================
// UI State Types
// ============================================================================

export type ExportPhase = 'idle' | 'starting' | 'processing' | 'completed' | 'failed' | 'cancelled'

export interface ExportState {
  /** Current phase of export */
  phase: ExportPhase
  /** Job ID for active export */
  jobId: string | null
  /** Progress percentage (0-100) */
  progress: number
  /** Download URL when completed */
  downloadUrl: string | null
  /** Error message if failed */
  error: string | null
}

export const initialExportState: ExportState = {
  phase: 'idle',
  jobId: null,
  progress: 0,
  downloadUrl: null,
  error: null,
}

// ============================================================================
// Preview State Types
// ============================================================================

export interface PreviewState {
  /** Whether preview is loading */
  isLoading: boolean
  /** Preview HTML content */
  html: string | null
  /** Error message if preview failed */
  error: string | null
}

export const initialPreviewState: PreviewState = {
  isLoading: false,
  html: null,
  error: null,
}

// ============================================================================
// Metadata Editing Types
// ============================================================================

export interface EbookMetadata {
  finalTitle: string
  finalSubtitle: string
  creditsText: string
}
