/**
 * Grid display for visual assets.
 *
 * Features:
 * - Responsive grid layout
 * - Empty state message
 * - Asset cards with delete and edit metadata capability
 */

import type { VisualAsset } from "../../types/visuals";
import { AssetCard } from "./AssetCard";

interface AssetGridProps {
  projectId: string;
  assets: VisualAsset[];
  onDeleteAsset?: (assetId: string) => void;
  onEditMetadata?: (assetId: string) => void;
}

export function AssetGrid({ projectId, assets, onDeleteAsset, onEditMetadata }: AssetGridProps) {
  if (assets.length === 0) {
    return (
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
        <h3 className="mt-2 text-sm font-medium text-gray-900">No images yet</h3>
        <p className="mt-1 text-sm text-gray-500">
          Upload images to build your visual library
        </p>
      </div>
    );
  }

  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4">
      {assets.map((asset) => (
        <AssetCard
          key={asset.id}
          projectId={projectId}
          asset={asset}
          onDelete={onDeleteAsset}
          onEditMetadata={onEditMetadata}
        />
      ))}
    </div>
  );
}
