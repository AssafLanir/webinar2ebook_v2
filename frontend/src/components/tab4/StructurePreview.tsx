import type { OutlineItem, Visual } from '../../types/project'

export interface StructurePreviewProps {
  chapters: OutlineItem[]
  visuals: Visual[]
}

export function StructurePreview({ chapters, visuals }: StructurePreviewProps) {
  const sortedChapters = [...chapters].sort((a, b) => a.order - b.order)
  const selectedVisuals = visuals.filter(v => v.selected)

  return (
    <div className="space-y-6">
      {/* Chapters Preview */}
      <div>
        <h4 className="font-medium text-gray-900 mb-3">Table of Contents</h4>
        {sortedChapters.length === 0 ? (
          <p className="text-sm text-gray-500 italic">
            No chapters defined yet. Add outline items in Tab 1 to see them here.
          </p>
        ) : (
          <ul className="space-y-1">
            {sortedChapters.map((chapter, index) => {
              const indent = (chapter.level - 1) * 16
              const isMainChapter = chapter.level === 1
              return (
                <li
                  key={chapter.id}
                  style={{ paddingLeft: indent }}
                  className={`text-sm ${isMainChapter ? 'font-medium text-gray-900' : 'text-gray-600'}`}
                >
                  {isMainChapter ? (
                    <span>Chapter {sortedChapters.filter((c, i) => c.level === 1 && i <= index).length}: {chapter.title}</span>
                  ) : (
                    <span>• {chapter.title}</span>
                  )}
                </li>
              )
            })}
          </ul>
        )}
      </div>

      {/* Selected Visuals Preview */}
      <div>
        <h4 className="font-medium text-gray-900 mb-3">
          Included Visuals ({selectedVisuals.length})
        </h4>
        {selectedVisuals.length === 0 ? (
          <p className="text-sm text-gray-500 italic">
            No visuals selected. Select visuals in Tab 2 to include them in the export.
          </p>
        ) : (
          <ul className="space-y-2">
            {selectedVisuals.map(visual => (
              <li key={visual.id} className="flex items-start gap-2 text-sm">
                <svg
                  className="w-4 h-4 text-blue-500 mt-0.5 flex-shrink-0"
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
                <div>
                  <span className="font-medium text-gray-900">{visual.title}</span>
                  {visual.isCustom && (
                    <span className="ml-2 text-xs bg-purple-100 text-purple-700 px-1.5 py-0.5 rounded">
                      Custom
                    </span>
                  )}
                  <p className="text-gray-500">{visual.description}</p>
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  )
}
