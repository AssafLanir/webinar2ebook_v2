import type { Edition } from '../../types/edition'
import { EDITION_LABELS, EDITION_DESCRIPTIONS, EDITION_RECOMMENDATION_REASONS } from '../../types/edition'

interface EditionSelectorProps {
  value: Edition
  onChange: (edition: Edition) => void
  recommendedEdition?: Edition
  showRecommendation?: boolean
  disabled?: boolean
}

export function EditionSelector({
  value,
  onChange,
  recommendedEdition,
  showRecommendation = true,
  disabled = false,
}: EditionSelectorProps) {
  const editions: Edition[] = ['qa', 'ideas']

  return (
    <div className="space-y-3">
      <label className="block text-sm font-medium text-gray-700">
        Output Edition
      </label>

      <div className="space-y-2">
        {editions.map((edition) => (
          <label
            key={edition}
            className={`
              relative flex items-start p-4 border rounded-lg cursor-pointer
              ${value === edition
                ? 'border-blue-500 bg-blue-50'
                : 'border-gray-200 hover:border-gray-300'
              }
              ${disabled ? 'opacity-50 cursor-not-allowed' : ''}
            `}
          >
            <input
              type="radio"
              name="edition"
              value={edition}
              checked={value === edition}
              onChange={() => onChange(edition)}
              disabled={disabled}
              className="h-4 w-4 mt-0.5 text-blue-600 border-gray-300 focus:ring-blue-500"
            />
            <div className="ml-3">
              <span className="block text-sm font-medium text-gray-900">
                {EDITION_LABELS[edition]}
              </span>
              <span className="block text-sm text-gray-500">
                {EDITION_DESCRIPTIONS[edition]}
              </span>
            </div>
          </label>
        ))}
      </div>

      {showRecommendation && recommendedEdition && value !== recommendedEdition && (
        <p className="text-sm text-gray-500">
          <span className="inline-flex items-center">
            <svg className="w-4 h-4 mr-1 text-blue-500" fill="currentColor" viewBox="0 0 20 20">
              <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clipRule="evenodd" />
            </svg>
            {EDITION_LABELS[recommendedEdition]} recommended — {EDITION_RECOMMENDATION_REASONS[recommendedEdition]}
          </span>
        </p>
      )}
    </div>
  )
}
