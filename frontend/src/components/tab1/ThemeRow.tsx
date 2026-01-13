import type { Theme } from '../../types/edition'
import { COVERAGE_COLORS, COVERAGE_LABELS } from '../../types/edition'

interface ThemeRowProps {
  theme: Theme
  onUpdate: (updates: Partial<Theme>) => void
  onRemove: () => void
}

export function ThemeRow({ theme, onUpdate: _onUpdate, onRemove }: ThemeRowProps) {
  // onUpdate is passed but not yet used - will be implemented for inline editing
  void _onUpdate
  return (
    <div className="flex items-start gap-3 p-3 bg-white border rounded-lg group">
      {/* Drag handle */}
      <div className="cursor-grab text-gray-400 hover:text-gray-600">
        <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 8h16M4 16h16" />
        </svg>
      </div>

      {/* Content */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <h4 className="font-medium text-gray-900 truncate">{theme.title}</h4>
          <span className={`px-2 py-0.5 text-xs font-medium rounded ${COVERAGE_COLORS[theme.coverage]}`}>
            {COVERAGE_LABELS[theme.coverage]}
          </span>
        </div>
        <p className="text-sm text-gray-500 truncate">{theme.one_liner}</p>
        {theme.coverage === 'weak' && (
          <p className="text-xs text-red-600 mt-1 flex items-center gap-1">
            <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
              <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
            </svg>
            Limited source material
          </p>
        )}
        <details className="mt-2">
          <summary className="text-xs text-gray-400 cursor-pointer hover:text-gray-600">
            {theme.supporting_segments.length} supporting segments
          </summary>
          <div className="mt-1 space-y-1">
            {theme.supporting_segments.slice(0, 3).map((seg, i) => (
              <p key={i} className="text-xs text-gray-500 truncate pl-2 border-l-2 border-gray-200">
                {seg.text_preview}
              </p>
            ))}
          </div>
        </details>
      </div>

      {/* Actions */}
      <button
        onClick={onRemove}
        className="opacity-0 group-hover:opacity-100 p-1 text-gray-400 hover:text-red-500"
        title="Remove theme"
      >
        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
        </svg>
      </button>
    </div>
  )
}
