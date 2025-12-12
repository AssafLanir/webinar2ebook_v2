import type { StyleConfig, AudienceType, ToneType, DepthLevel } from '../../types/project'
import { Select } from '../common/Select'

export interface StyleControlsProps {
  config: StyleConfig
  onChange: (updates: Partial<StyleConfig>) => void
}

const audienceOptions = [
  { value: 'general', label: 'General Audience' },
  { value: 'technical', label: 'Technical' },
  { value: 'executive', label: 'Executive' },
  { value: 'academic', label: 'Academic' },
]

const toneOptions = [
  { value: 'formal', label: 'Formal' },
  { value: 'conversational', label: 'Conversational' },
  { value: 'instructional', label: 'Instructional' },
  { value: 'persuasive', label: 'Persuasive' },
]

const depthOptions = [
  { value: 'overview', label: 'Overview' },
  { value: 'moderate', label: 'Moderate' },
  { value: 'comprehensive', label: 'Comprehensive' },
]

export function StyleControls({ config, onChange }: StyleControlsProps) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
      <Select
        label="Target Audience"
        value={config.audience ?? 'general'}
        onChange={value => onChange({ audience: value as AudienceType })}
        options={audienceOptions}
      />

      <Select
        label="Tone"
        value={config.tone ?? 'conversational'}
        onChange={value => onChange({ tone: value as ToneType })}
        options={toneOptions}
      />

      <Select
        label="Depth Level"
        value={config.depth ?? 'moderate'}
        onChange={value => onChange({ depth: value as DepthLevel })}
        options={depthOptions}
      />

      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">
          Target Pages
        </label>
        <input
          type="number"
          min={1}
          max={500}
          value={config.targetPages}
          onChange={e => onChange({ targetPages: parseInt(e.target.value) || 1 })}
          className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm
            focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
        />
      </div>
    </div>
  )
}
