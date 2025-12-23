/**
 * Visual asset card component.
 *
 * Displays:
 * - Thumbnail image
 * - Filename and caption
 * - Dimensions and size
 * - Action buttons: Download, Copy URL, Copy Markdown, Delete
 */

import { useState } from "react";
import type { VisualAsset } from "../../types/visuals";
import { getAssetContentUrl } from "../../services/visualsApi";
import { formatFileSize } from "../../utils/formatFileSize";

interface AssetCardProps {
  projectId: string;
  asset: VisualAsset;
  onDelete?: (assetId: string) => void;
}

export function AssetCard({ projectId, asset, onDelete }: AssetCardProps) {
  const thumbnailUrl = getAssetContentUrl(projectId, asset.id, "thumb");
  const fullUrl = getAssetContentUrl(projectId, asset.id, "full");
  const [copyFeedback, setCopyFeedback] = useState<string | null>(null);

  const handleDelete = () => {
    if (onDelete && window.confirm(`Delete "${asset.caption || asset.filename}"?`)) {
      onDelete(asset.id);
    }
  };

  // T040: Download handler - fetches full size image and triggers browser download
  const handleDownload = async () => {
    try {
      const response = await fetch(fullUrl);
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = asset.original_filename || asset.filename;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (error) {
      console.error("Download failed:", error);
    }
  };

  // T041: Copy URL to clipboard
  const handleCopyUrl = async () => {
    try {
      await navigator.clipboard.writeText(fullUrl);
      setCopyFeedback("URL copied!");
      setTimeout(() => setCopyFeedback(null), 2000);
    } catch (error) {
      console.error("Copy URL failed:", error);
    }
  };


  return (
    <div className="bg-white border border-gray-200 rounded-lg overflow-hidden shadow-sm hover:shadow-md transition-shadow">
      {/* Thumbnail */}
      <div className="aspect-square bg-gray-100 relative">
        <img
          src={thumbnailUrl}
          alt={asset.alt_text || asset.caption || asset.filename}
          className="w-full h-full object-cover"
          loading="lazy"
        />

        {/* Delete button overlay */}
        {onDelete && (
          <button
            onClick={handleDelete}
            className="absolute top-2 right-2 p-1.5 bg-red-500 text-white rounded-full opacity-0 group-hover:opacity-100 hover:bg-red-600 transition-all shadow-md"
            style={{ opacity: 1 }} // Always visible for now
            title="Delete asset"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
              />
            </svg>
          </button>
        )}
      </div>

      {/* Info */}
      <div className="p-3">
        <p className="text-sm font-medium text-gray-900 truncate" title={asset.caption || asset.filename}>
          {asset.caption || asset.filename}
        </p>

        <div className="mt-1 flex items-center gap-2 text-xs text-gray-500">
          {asset.width && asset.height && (
            <span>{asset.width}×{asset.height}</span>
          )}
          {asset.size_bytes && (
            <>
              <span>•</span>
              <span>{formatFileSize(asset.size_bytes)}</span>
            </>
          )}
        </div>

        {/* Action buttons */}
        <div className="mt-3 flex items-center gap-1 flex-wrap">
          {/* Download button (T039) */}
          <button
            onClick={handleDownload}
            className="px-2 py-1 text-xs bg-gray-100 hover:bg-gray-200 text-gray-700 rounded transition-colors"
            title="Download full size image"
          >
            <svg className="w-3.5 h-3.5 inline-block mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
            </svg>
            Download
          </button>

          {/* Copy URL button (T041) */}
          <button
            onClick={handleCopyUrl}
            className="px-2 py-1 text-xs bg-gray-100 hover:bg-gray-200 text-gray-700 rounded transition-colors"
            title="Copy image URL to clipboard"
          >
            <svg className="w-3.5 h-3.5 inline-block mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1" />
            </svg>
            URL
          </button>
        </div>

        {/* Copy feedback toast */}
        {copyFeedback && (
          <div className="mt-2 text-xs text-green-600 font-medium">
            {copyFeedback}
          </div>
        )}
      </div>
    </div>
  );
}
