/**
 * AssetPickerModal component for Tab 2 Visuals.
 *
 * Modal dialog to select an asset for assignment to an opportunity.
 * Shows grid of available assets with selection capability.
 */

import { useState } from "react";
import type { VisualAsset, VisualOpportunity } from "../../types/visuals";
import { getAssetContentUrl } from "../../services/visualsApi";

interface AssetPickerModalProps {
  projectId: string;
  opportunity: VisualOpportunity;
  assets: VisualAsset[];
  onSelect: (assetId: string) => void;
  onCancel: () => void;
}

export function AssetPickerModal({
  projectId,
  opportunity,
  assets,
  onSelect,
  onCancel,
}: AssetPickerModalProps) {
  const [selectedAssetId, setSelectedAssetId] = useState<string | null>(null);

  const handleConfirm = () => {
    if (selectedAssetId) {
      onSelect(selectedAssetId);
    }
  };

  // Handle backdrop click
  const handleBackdropClick = (e: React.MouseEvent) => {
    if (e.target === e.currentTarget) {
      onCancel();
    }
  };

  // Handle escape key
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Escape") {
      onCancel();
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
      onClick={handleBackdropClick}
      onKeyDown={handleKeyDown}
      role="dialog"
      aria-modal="true"
      aria-labelledby="picker-title"
    >
      <div className="bg-white rounded-lg shadow-xl w-full max-w-2xl max-h-[80vh] flex flex-col">
        {/* Header */}
        <div className="px-6 py-4 border-b border-gray-200">
          <h2 id="picker-title" className="text-lg font-semibold text-gray-900">
            Select Image for "{opportunity.title}"
          </h2>
          <p className="text-sm text-gray-500 mt-1">
            Choose an image from your library to assign to this visual opportunity.
          </p>
        </div>

        {/* Body - scrollable asset grid */}
        <div className="flex-1 overflow-y-auto p-6">
          {assets.length === 0 ? (
            <div className="text-center py-12">
              <svg
                className="mx-auto h-12 w-12 text-gray-400"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z"
                />
              </svg>
              <h3 className="mt-2 text-sm font-medium text-gray-900">No images available</h3>
              <p className="mt-1 text-sm text-gray-500">
                Upload images to your library first.
              </p>
            </div>
          ) : (
            <div className="grid grid-cols-3 sm:grid-cols-4 gap-4">
              {assets.map((asset) => (
                <button
                  key={asset.id}
                  onClick={() => setSelectedAssetId(asset.id)}
                  className={`relative aspect-square rounded-lg overflow-hidden border-2 transition-all ${
                    selectedAssetId === asset.id
                      ? "border-blue-500 ring-2 ring-blue-200"
                      : "border-gray-200 hover:border-gray-300"
                  }`}
                >
                  <img
                    src={getAssetContentUrl(projectId, asset.id, "thumb")}
                    alt={asset.alt_text || asset.caption || asset.filename}
                    className="w-full h-full object-cover"
                    loading="lazy"
                  />
                  {selectedAssetId === asset.id && (
                    <div className="absolute inset-0 bg-blue-500/20 flex items-center justify-center">
                      <svg
                        className="w-8 h-8 text-blue-600"
                        fill="currentColor"
                        viewBox="0 0 20 20"
                      >
                        <path
                          fillRule="evenodd"
                          d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
                          clipRule="evenodd"
                        />
                      </svg>
                    </div>
                  )}
                  <div className="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-black/60 to-transparent p-2">
                    <p className="text-xs text-white truncate">
                      {asset.caption || asset.filename}
                    </p>
                  </div>
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-gray-200 flex justify-end gap-3">
          <button
            onClick={onCancel}
            className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={handleConfirm}
            disabled={!selectedAssetId}
            className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            Assign Image
          </button>
        </div>
      </div>
    </div>
  );
}
