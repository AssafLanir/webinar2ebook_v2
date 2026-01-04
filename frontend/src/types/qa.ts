/**
 * QA (Quality Assessment) Types
 *
 * Types for draft quality analysis: reports, issues, scores, and job tracking.
 * Matches backend models and specs/008-draft-quality/schemas/qa_report.schema.json
 */

// ============================================================================
// Enums and Literals
// ============================================================================

export type IssueSeverity = 'critical' | 'warning' | 'info'

export type IssueType = 'repetition' | 'structure' | 'clarity' | 'faithfulness' | 'completeness'

export type QAJobStatus = 'queued' | 'running' | 'completed' | 'failed' | 'cancelled'

// ============================================================================
// Issue Counts
// ============================================================================

export interface IssueCounts {
  critical: number
  warning: number
  info: number
}

// ============================================================================
// Rubric Scores
// ============================================================================

export interface RubricScores {
  /** Heading hierarchy and chapter balance score (1-100) */
  structure: number
  /** Sentence length, passive voice, jargon score (1-100) */
  clarity: number
  /** Alignment with source material score (1-100) */
  faithfulness: number
  /** Inverse of repetition: 100 = no repetition (1-100) */
  repetition: number
  /** Coverage of source topics score (1-100) */
  completeness: number
}

// ============================================================================
// QA Issue
// ============================================================================

export interface QAIssue {
  /** Unique issue identifier */
  id: string
  /** Issue severity level */
  severity: IssueSeverity
  /** Category of the issue */
  issue_type: IssueType
  /** Chapter index (0-based), null if global */
  chapter_index: number | null
  /** Heading where issue occurs */
  heading: string | null
  /** Text excerpt showing location */
  location: string | null
  /** Human-readable issue description */
  message: string
  /** Actionable fix suggestion */
  suggestion: string | null
  /** Additional issue-specific data */
  metadata: Record<string, unknown> | null
}

// ============================================================================
// QA Report
// ============================================================================

export interface QAReport {
  /** Unique report identifier */
  id: string
  /** Reference to the project */
  project_id: string
  /** Hash of draft text for cache invalidation */
  draft_hash: string
  /** Overall quality score (1-100) */
  overall_score: number
  /** Breakdown by category */
  rubric_scores: RubricScores
  /** List of detected quality issues (max 300) */
  issues: QAIssue[]
  /** Counts by severity (always accurate, even if truncated) */
  issue_counts: IssueCounts
  /** True if issues list was capped at max */
  truncated: boolean
  /** Actual total count (may exceed issues array length) */
  total_issue_count: number
  /** When the report was generated */
  generated_at: string
  /** Analysis duration in milliseconds */
  analysis_duration_ms: number
  /** Schema version for migrations */
  version: string
}

// ============================================================================
// API Response Types
// ============================================================================

export interface QAAnalyzeData {
  /** Job ID for polling status */
  job_id: string
}

export interface QAJobStatusData {
  job_id: string
  status: QAJobStatus
  /** Progress percentage (0-100) */
  progress?: number
  /** Present when status is completed */
  report?: QAReport
  /** Present when status is failed */
  error_message?: string
}

export interface QAReportData {
  /** The QA report (null if not yet generated) */
  report: QAReport | null
}

// ============================================================================
// UI State Types
// ============================================================================

export type QAPhase = 'idle' | 'analyzing' | 'completed' | 'failed'

export interface QAState {
  /** Current phase of QA analysis */
  phase: QAPhase
  /** Job ID for active analysis */
  jobId: string | null
  /** Progress percentage (0-100) */
  progress: number
  /** Error message if failed */
  error: string | null
  /** The QA report (null if not yet generated) */
  report: QAReport | null
  /** Whether the QA panel is expanded */
  isExpanded: boolean
}

export const initialQAState: QAState = {
  phase: 'idle',
  jobId: null,
  progress: 0,
  error: null,
  report: null,
  isExpanded: false,
}

// ============================================================================
// Helper Functions
// ============================================================================

/**
 * Get color class for severity badge
 */
export function getSeverityColor(severity: IssueSeverity): string {
  switch (severity) {
    case 'critical':
      return 'text-red-600 bg-red-100'
    case 'warning':
      return 'text-yellow-600 bg-yellow-100'
    case 'info':
      return 'text-blue-600 bg-blue-100'
  }
}

/**
 * Get icon name for severity
 */
export function getSeverityIcon(severity: IssueSeverity): string {
  switch (severity) {
    case 'critical':
      return 'XCircle'
    case 'warning':
      return 'AlertTriangle'
    case 'info':
      return 'Info'
  }
}

/**
 * Get score quality label
 */
export function getScoreLabel(score: number): string {
  if (score >= 90) return 'Excellent'
  if (score >= 70) return 'Good'
  if (score >= 50) return 'Needs Improvement'
  return 'Poor'
}

/**
 * Get color class for score
 */
export function getScoreColor(score: number): string {
  if (score >= 90) return 'text-green-600'
  if (score >= 70) return 'text-blue-600'
  if (score >= 50) return 'text-yellow-600'
  return 'text-red-600'
}
