// Visual assets + visual opportunities (mirrors backend/src/models/visuals.py).

import type { VisualType, VisualSourcePolicy } from "./style";

export type VisualAssetOrigin = "client_provided" | "user_uploaded" | "generated" | "external_link";

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
}
