/**
 * Modal for editing visual asset metadata (caption, alt_text).
 *
 * T043: Allows user to edit caption and alt text for an uploaded image.
 */

import { useState } from "react";
import type { VisualAsset } from "../../types/visuals";

interface AssetMetadataModalProps {
  asset: VisualAsset;
  onSave: (assetId: string, updates: { caption?: string; alt_text?: string }) => void;
  onCancel: () => void;
}

export function AssetMetadataModal({ asset, onSave, onCancel }: AssetMetadataModalProps) {
  const [caption, setCaption] = useState(asset.caption || "");
  const [altText, setAltText] = useState(asset.alt_text || "");

  const handleSave = () => {
    onSave(asset.id, {
      caption: caption.trim() || undefined,
      alt_text: altText.trim() || undefined,
    });
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Escape") {
      onCancel();
    }
  };

  return (
    <div
      className="fixed inset-0 bg-black/50 flex items-center justify-center z-50"
      onClick={onCancel}
      onKeyDown={handleKeyDown}
    >
      <div
        className="bg-white rounded-lg shadow-xl max-w-md w-full mx-4"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="px-6 py-4 border-b border-gray-200">
          <h3 className="text-lg font-semibold text-gray-900">Edit Metadata</h3>
          <p className="text-sm text-gray-500 mt-1">{asset.filename}</p>
        </div>

        {/* Form */}
        <div className="px-6 py-4 space-y-4">
          {/* Caption field */}
          <div>
            <label htmlFor="caption" className="block text-sm font-medium text-gray-700 mb-1">
              Caption
            </label>
            <input
              type="text"
              id="caption"
              value={caption}
              onChange={(e) => setCaption(e.target.value)}
              placeholder="Enter a caption for this image"
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              autoFocus
            />
            <p className="text-xs text-gray-500 mt-1">
              Displayed below the image in the library
            </p>
          </div>

          {/* Alt text field */}
          <div>
            <label htmlFor="alt-text" className="block text-sm font-medium text-gray-700 mb-1">
              Alt Text
            </label>
            <textarea
              id="alt-text"
              value={altText}
              onChange={(e) => setAltText(e.target.value)}
              placeholder="Describe the image for accessibility"
              rows={3}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-none"
            />
            <p className="text-xs text-gray-500 mt-1">
              Used for screen readers and when image cannot load
            </p>
          </div>
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-gray-200 flex justify-end gap-3">
          <button
            onClick={onCancel}
            className="px-4 py-2 text-sm text-gray-700 hover:bg-gray-100 rounded-md transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={handleSave}
            className="px-4 py-2 text-sm bg-blue-600 text-white hover:bg-blue-700 rounded-md transition-colors"
          >
            Save
          </button>
        </div>
      </div>
    </div>
  );
}
