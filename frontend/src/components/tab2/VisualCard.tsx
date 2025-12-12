import type { Visual } from '../../types/project'

export interface VisualCardProps {
  visual: Visual
  onToggle: () => void
}

export function VisualCard({ visual, onToggle }: VisualCardProps) {
  return (
    <div
      className={`
        relative p-4 rounded-lg border-2 transition-all cursor-pointer
        ${
          visual.selected
            ? 'border-blue-500 bg-blue-50'
            : 'border-gray-200 bg-white hover:border-gray-300'
        }
      `}
      onClick={onToggle}
    >
      {/* Selection indicator */}
      <div
        className={`
          absolute top-2 right-2 w-6 h-6 rounded-full flex items-center justify-center
          transition-colors
          ${visual.selected ? 'bg-blue-500 text-white' : 'bg-gray-200 text-gray-400'}
        `}
      >
        {visual.selected && (
          <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
            <path
              fillRule="evenodd"
              d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
              clipRule="evenodd"
            />
          </svg>
        )}
      </div>

      {/* Visual placeholder icon */}
      <div className="w-full h-24 bg-gray-100 rounded-md mb-3 flex items-center justify-center">
        <svg
          className={`w-12 h-12 ${visual.selected ? 'text-blue-400' : 'text-gray-300'}`}
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={1.5}
            d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z"
          />
        </svg>
      </div>

      {/* Title and description */}
      <h3 className="font-medium text-gray-900 mb-1">{visual.title}</h3>
      <p className="text-sm text-gray-500 line-clamp-2">{visual.description}</p>

      {/* Custom badge */}
      {visual.isCustom && (
        <span className="inline-block mt-2 px-2 py-0.5 text-xs font-medium bg-purple-100 text-purple-700 rounded">
          Custom
        </span>
      )}
    </div>
  )
}
