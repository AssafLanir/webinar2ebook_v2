/**
 * Visual asset card component.
 *
 * Displays:
 * - Thumbnail image
 * - Filename and caption
 * - Dimensions and size
 * - Delete button
 */

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

  const handleDelete = () => {
    if (onDelete && window.confirm(`Delete "${asset.caption || asset.filename}"?`)) {
      onDelete(asset.id);
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
      </div>
    </div>
  );
}
