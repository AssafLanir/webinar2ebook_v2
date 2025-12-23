// Visual assets + visual opportunities (mirrors backend/src/models/visuals.py).

import type { VisualType, VisualSourcePolicy } from "./style";

// Extended for Spec 005 compatibility - includes aliases
export type VisualAssetOrigin =
  | "client_provided"
  | "user_uploaded"
  | "client_upload" // Alias for Spec 005
  | "generated"
  | "ai_generated" // Alias for Spec 005
  | "external_link"
  | "external_url"; // Alias for Spec 005

export interface VisualAsset {
  id: string;
  filename: string;
  media_type: string; // e.g. image/png
  origin?: VisualAssetOrigin;

  source_url?: string | null;
  storage_key?: string | null;

  width?: number | null;
  height?: number | null;

  alt_text?: string | null;
  tags?: string[];

  // New fields for Spec 005 (Tab 2 Visuals)
  original_filename?: string | null; // Original upload filename before sanitization
  size_bytes?: number | null; // File size in bytes
  caption?: string | null; // Display caption (defaults to filename stem)
  sha256?: string | null; // SHA-256 hash of original bytes
  created_at?: string | null; // ISO 8601 timestamp of upload
}

export type VisualPlacement = "after_heading" | "inline" | "end_of_section" | "end_of_chapter" | "sidebar";

export interface VisualOpportunity {
  id: string;
  chapter_index: number; // 1-based
  section_path?: string | null;
  placement?: VisualPlacement;

  visual_type: VisualType;
  source_policy?: VisualSourcePolicy;

  title: string;
  prompt: string;
  caption: string;

  required?: boolean;
  candidate_asset_ids?: string[];

  confidence?: number; // 0..1
  rationale?: string | null;
}

export interface VisualPlan {
  opportunities: VisualOpportunity[];
  assets?: VisualAsset[];
  assignments?: VisualAssignment[];
}

// Assignment status (Spec 005)
export type VisualAssignmentStatus = "assigned" | "skipped";

/**
 * Links a VisualOpportunity to a VisualAsset (or marks it skipped).
 *
 * Lifecycle rules:
 * - Unassigned: No VisualAssignment record exists
 * - Assigned: Record with status="assigned" and asset_id populated
 * - Skipped: Record with status="skipped" and asset_id=null/undefined
 */
export interface VisualAssignment {
  opportunity_id: string; // References VisualOpportunity.id
  status: VisualAssignmentStatus;
  asset_id?: string | null; // References VisualAsset.id (required when assigned)
  user_notes?: string | null; // Optional user comment
  updated_at?: string; // ISO 8601 timestamp
}
