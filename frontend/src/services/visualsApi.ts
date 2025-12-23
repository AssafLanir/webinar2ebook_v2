/**
 * API service for visual asset operations.
 *
 * Handles:
 * - Uploading images to the visual library
 * - Building URLs to serve asset content
 */

import type { VisualAsset } from "../types/visuals";

const API_BASE = "http://localhost:8000";

interface UploadResponse {
  data: {
    assets: VisualAsset[];
  } | null;
  error: {
    code: string;
    message: string;
  } | null;
}

interface DeleteResponse {
  data: {
    deleted: boolean;
    files_removed: number;
  } | null;
  error: {
    code: string;
    message: string;
  } | null;
}

export class VisualsApiError extends Error {
  code: string;

  constructor(code: string, message: string) {
    super(message);
    this.code = code;
    this.name = "VisualsApiError";
  }
}

/**
 * Upload images to a project's visual library.
 *
 * @param projectId - Project ID
 * @param files - Array of File objects to upload
 * @returns Array of created VisualAsset objects
 * @throws VisualsApiError on validation or server errors
 */
export async function uploadVisualAssets(
  projectId: string,
  files: File[]
): Promise<VisualAsset[]> {
  const formData = new FormData();
  for (const file of files) {
    formData.append("files", file);
  }

  const response = await fetch(
    `${API_BASE}/api/projects/${projectId}/visuals/assets/upload`,
    {
      method: "POST",
      body: formData,
    }
  );

  const data: UploadResponse = await response.json();

  if (data.error) {
    throw new VisualsApiError(data.error.code, data.error.message);
  }

  if (!data.data?.assets) {
    throw new VisualsApiError("UNKNOWN_ERROR", "No assets in response");
  }

  return data.data.assets;
}

/**
 * Get the URL to serve an asset's content.
 *
 * @param projectId - Project ID
 * @param assetId - Asset UUID
 * @param size - "thumb" (default) or "full"
 * @returns URL string for the asset content
 */
export function getAssetContentUrl(
  projectId: string,
  assetId: string,
  size: "thumb" | "full" = "thumb"
): string {
  return `${API_BASE}/api/projects/${projectId}/visuals/assets/${assetId}/content?size=${size}`;
}

/**
 * Delete a visual asset from the project.
 *
 * @param projectId - Project ID
 * @param assetId - Asset UUID
 * @returns True if deleted successfully
 * @throws VisualsApiError on errors
 */
export async function deleteVisualAsset(
  projectId: string,
  assetId: string
): Promise<boolean> {
  const response = await fetch(
    `${API_BASE}/api/projects/${projectId}/visuals/assets/${assetId}`,
    {
      method: "DELETE",
    }
  );

  const data: DeleteResponse = await response.json();

  if (data.error) {
    throw new VisualsApiError(data.error.code, data.error.message);
  }

  return data.data?.deleted ?? false;
}
