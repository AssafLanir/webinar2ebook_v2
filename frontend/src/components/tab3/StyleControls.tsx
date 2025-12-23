import type { StyleConfig, TotalLengthPreset, DetailLevel } from '../../types/style'
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
]

const detailLevelOptions = [
  { value: 'concise', label: 'Concise' },
  { value: 'balanced', label: 'Balanced' },
  { value: 'detailed', label: 'Detailed' },
]

export function StyleControls({ config, onChange }: StyleControlsProps) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
      <Select
        label="Total Draft Length"
        value={config.total_length_preset ?? 'standard'}
        onChange={value => onChange({ total_length_preset: value as TotalLengthPreset })}
        options={totalLengthOptions}
      />

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
