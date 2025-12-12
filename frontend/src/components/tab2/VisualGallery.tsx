import type { Visual } from '../../types/project'
import { VisualCard } from './VisualCard'

export interface VisualGalleryProps {
  visuals: Visual[]
  onToggleSelection: (id: string) => void
}

export function VisualGallery({ visuals, onToggleSelection }: VisualGalleryProps) {
  const sortedVisuals = [...visuals].sort((a, b) => (a.order ?? 0) - (b.order ?? 0))
  const selectedCount = visuals.filter(v => v.selected).length

  return (
    <div>
      <div className="flex justify-between items-center mb-4">
        <p className="text-sm text-gray-500">
          Click on a visual to toggle its selection for export.
        </p>
        <span className="text-sm font-medium text-blue-600">
          {selectedCount} of {visuals.length} selected
        </span>
      </div>

      {sortedVisuals.length === 0 ? (
        <p className="text-gray-500 text-center py-8">
          No visuals available. Add custom visuals below.
        </p>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {sortedVisuals.map(visual => (
            <VisualCard
              key={visual.id}
              visual={visual}
              onToggle={() => onToggleSelection(visual.id)}
            />
          ))}
        </div>
      )}
    </div>
  )
}
