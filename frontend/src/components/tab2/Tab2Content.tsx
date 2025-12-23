/**
 * Tab 2: Visuals Workbench
 *
 * Features:
 * - Upload images to visual library
 * - View uploaded assets as thumbnails
 * - Delete assets
 * - Auto-save after changes
 */

import { useState, useCallback, useRef, useEffect } from "react";
import { useProject } from "../../context/ProjectContext";
import { Card } from "../common/Card";
import { FileUploadDropzone } from "./FileUploadDropzone";
import { AssetGrid } from "./AssetGrid";
import {
  uploadVisualAssets,
  deleteVisualAsset,
  VisualsApiError,
} from "../../services/visualsApi";

// Debounce delay for auto-save (ms)
const SAVE_DEBOUNCE_MS = 1500;

export function Tab2Content() {
  const { state, dispatch, saveProject } = useProject();
  const { project } = state;

  const [isUploading, setIsUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);

  // Debounced save ref
  const saveTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Trigger debounced save
  const debouncedSave = useCallback(() => {
    if (saveTimeoutRef.current) {
      clearTimeout(saveTimeoutRef.current);
    }
    saveTimeoutRef.current = setTimeout(() => {
      saveProject();
    }, SAVE_DEBOUNCE_MS);
  }, [saveProject]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (saveTimeoutRef.current) {
        clearTimeout(saveTimeoutRef.current);
      }
    };
  }, []);

  if (!project) return null;

  const assets = project.visualPlan?.assets ?? [];
  const assetCount = assets.length;
  const maxAssets = 10;
  const canUpload = assetCount < maxAssets;

  const handleFilesSelected = async (files: File[]) => {
    if (!canUpload) {
      setUploadError(`Maximum ${maxAssets} assets per project`);
      return;
    }

    setIsUploading(true);
    setUploadError(null);

    try {
      const uploadedAssets = await uploadVisualAssets(project.id, files);

      // Add to state
      dispatch({ type: "ADD_VISUAL_ASSETS", payload: uploadedAssets });

      // Trigger auto-save
      debouncedSave();
    } catch (error) {
      if (error instanceof VisualsApiError) {
        setUploadError(error.message);
      } else {
        setUploadError("Upload failed. Please try again.");
      }
    } finally {
      setIsUploading(false);
    }
  };

  const handleDeleteAsset = async (assetId: string) => {
    setIsDeleting(true);

    try {
      // Delete from server (GridFS)
      await deleteVisualAsset(project.id, assetId);

      // Remove from state
      dispatch({ type: "REMOVE_VISUAL_ASSET", payload: assetId });

      // Trigger auto-save
      debouncedSave();
    } catch (error) {
      if (error instanceof VisualsApiError) {
        setUploadError(`Delete failed: ${error.message}`);
      } else {
        setUploadError("Delete failed. Please try again.");
      }
    } finally {
      setIsDeleting(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Upload Section */}
      <Card title="Upload Images">
        <div className="space-y-4">
          <div className="flex items-center justify-between text-sm text-gray-500">
            <span>
              {assetCount} of {maxAssets} images uploaded
            </span>
            {isUploading && (
              <span className="flex items-center gap-2 text-blue-600">
                <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
                  <circle
                    className="opacity-25"
                    cx="12"
                    cy="12"
                    r="10"
                    stroke="currentColor"
                    strokeWidth="4"
                    fill="none"
                  />
                  <path
                    className="opacity-75"
                    fill="currentColor"
                    d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                  />
                </svg>
                Uploading...
              </span>
            )}
          </div>

          <FileUploadDropzone
            onFilesSelected={handleFilesSelected}
            disabled={!canUpload || isUploading}
            maxFiles={maxAssets - assetCount}
          />

          {uploadError && (
            <div className="p-3 bg-red-50 border border-red-200 rounded-md text-sm text-red-700">
              {uploadError}
              <button
                onClick={() => setUploadError(null)}
                className="ml-2 text-red-500 hover:text-red-700"
              >
                Dismiss
              </button>
            </div>
          )}
        </div>
      </Card>

      {/* Library Section */}
      <Card title="Visual Library">
        <div className="relative">
          {isDeleting && (
            <div className="absolute inset-0 bg-white/50 flex items-center justify-center z-10">
              <span className="text-gray-500">Deleting...</span>
            </div>
          )}

          <AssetGrid
            projectId={project.id}
            assets={assets}
            onDeleteAsset={handleDeleteAsset}
          />
        </div>
      </Card>

      {/* Visual Opportunities Section - placeholder for future US2 */}
      {project.visualPlan?.opportunities &&
        project.visualPlan.opportunities.length > 0 && (
          <Card title="Visual Opportunities">
            <p className="text-sm text-gray-500">
              {project.visualPlan.opportunities.length} visual opportunities
              from your draft. Assignment feature coming soon.
            </p>
          </Card>
        )}
    </div>
  );
}
