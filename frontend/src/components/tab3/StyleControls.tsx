import type { StyleConfig } from '../../types/style'
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

const chapterLengthOptions = [
  { value: 'short', label: 'Short' },
  { value: 'medium', label: 'Medium' },
  { value: 'long', label: 'Long' },
]

export function StyleControls({ config, onChange }: StyleControlsProps) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
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

      <Select
        label="Chapter Length"
        value={config.chapter_length_target ?? 'medium'}
        onChange={value => onChange({ chapter_length_target: value as StyleConfig['chapter_length_target'] })}
        options={chapterLengthOptions}
      />

      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">
          Target Chapters
        </label>
        <input
          type="number"
          min={1}
          max={30}
          value={config.chapter_count_target ?? 8}
          onChange={e => onChange({ chapter_count_target: parseInt(e.target.value) || 8 })}
          className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm
            focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
        />
      </div>
    </div>
  )
}
