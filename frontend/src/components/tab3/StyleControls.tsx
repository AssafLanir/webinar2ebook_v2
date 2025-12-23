import type { StyleConfig, TotalLengthPreset, DetailLevel } from '../../types/style'
import { MIN_CUSTOM_WORDS, MAX_CUSTOM_WORDS } from '../../types/style'
import { Select } from '../common/Select'

export interface StyleControlsProps {
  config: StyleConfig
  onChange: (updates: Partial<StyleConfig>) => void
}

// Options based on the new comprehensive StyleConfig enums
const toneOptions = [
  { value: 'professional', label: 'Professional' },
  { value: 'friendly', label: 'Friendly' },
  { value: 'authoritative', label: 'Authoritative' },
  { value: 'inspirational', label: 'Inspirational' },
  { value: 'conversational', label: 'Conversational' },
]

const targetAudienceOptions = [
  { value: 'beginners', label: 'Beginners' },
  { value: 'intermediate', label: 'Intermediate' },
  { value: 'experts', label: 'Experts' },
  { value: 'mixed', label: 'Mixed' },
]

const bookFormatOptions = [
  { value: 'guide', label: 'Guide' },
  { value: 'tutorial', label: 'Tutorial' },
  { value: 'ebook_marketing', label: 'Marketing eBook' },
  { value: 'executive_brief', label: 'Executive Brief' },
  { value: 'course_notes', label: 'Course Notes' },
  { value: 'whitepaper', label: 'Whitepaper' },
]

const totalLengthOptions = [
  { value: 'brief', label: 'Brief (~2,000 words)' },
  { value: 'standard', label: 'Standard (~5,000 words)' },
  { value: 'comprehensive', label: 'Comprehensive (~10,000 words)' },
  { value: 'custom', label: 'Custom' },
]

const detailLevelOptions = [
  { value: 'concise', label: 'Concise' },
  { value: 'balanced', label: 'Balanced' },
  { value: 'detailed', label: 'Detailed' },
]

export function StyleControls({ config, onChange }: StyleControlsProps) {
  const isCustomLength = config.total_length_preset === 'custom'

  const handlePresetChange = (value: string) => {
    const preset = value as TotalLengthPreset
    if (preset === 'custom') {
      // Set default custom value when switching to custom
      onChange({
        total_length_preset: preset,
        total_target_words: config.total_target_words ?? 5000,
      })
    } else {
      // Clear custom value when switching away from custom
      onChange({
        total_length_preset: preset,
        total_target_words: null,
      })
    }
  }

  const handleCustomWordsChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value
    if (value === '') {
      onChange({ total_target_words: null })
    } else {
      const numValue = parseInt(value, 10)
      if (!isNaN(numValue)) {
        onChange({ total_target_words: numValue })
      }
    }
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
      <div className="space-y-2">
        <Select
          label="Total Draft Length"
          value={config.total_length_preset ?? 'standard'}
          onChange={handlePresetChange}
          options={totalLengthOptions}
        />
        {isCustomLength && (
          <div className="mt-2">
            <label className="block text-sm font-medium text-slate-300 mb-1">
              Target Word Count
            </label>
            <input
              type="number"
              min={MIN_CUSTOM_WORDS}
              max={MAX_CUSTOM_WORDS}
              step={100}
              value={config.total_target_words ?? ''}
              onChange={handleCustomWordsChange}
              placeholder={`${MIN_CUSTOM_WORDS.toLocaleString()} - ${MAX_CUSTOM_WORDS.toLocaleString()}`}
              className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-slate-200 text-sm focus:outline-none focus:ring-2 focus:ring-cyan-500 focus:border-transparent"
            />
            <p className="mt-1 text-xs text-slate-500">
              Range: {MIN_CUSTOM_WORDS.toLocaleString()} - {MAX_CUSTOM_WORDS.toLocaleString()} words
            </p>
          </div>
        )}
      </div>

      <Select
        label="Detail Level"
        value={config.detail_level ?? 'balanced'}
        onChange={value => onChange({ detail_level: value as DetailLevel })}
        options={detailLevelOptions}
      />

      <Select
        label="Target Audience"
        value={config.target_audience ?? 'mixed'}
        onChange={value => onChange({ target_audience: value as StyleConfig['target_audience'] })}
        options={targetAudienceOptions}
      />

      <Select
        label="Tone"
        value={config.tone ?? 'professional'}
        onChange={value => onChange({ tone: value as StyleConfig['tone'] })}
        options={toneOptions}
      />

      <Select
        label="Book Format"
        value={config.book_format ?? 'guide'}
        onChange={value => onChange({ book_format: value as StyleConfig['book_format'] })}
        options={bookFormatOptions}
      />
    </div>
  )
}
