import { useState } from 'react'
import { useProject } from '../../context/ProjectContext'
import { Card } from '../common/Card'
import { Select } from '../common/Select'
import { StyleControls } from './StyleControls'
import { DraftEditor } from './DraftEditor'
import { STYLE_PRESETS } from '../../constants/stylePresets'
import type { StyleConfig, StyleConfigEnvelope } from '../../types/style'
import { DEFAULT_STYLE_CONFIG } from '../../types/project'

export function Tab3Content() {
  const { state, dispatch } = useProject()
  const { project } = state
  const [showCustomize, setShowCustomize] = useState(false)

  if (!project) return null

  // Get current style config as envelope
  const styleEnvelope: StyleConfigEnvelope =
    project.styleConfig && 'style' in project.styleConfig
      ? (project.styleConfig as StyleConfigEnvelope)
      : DEFAULT_STYLE_CONFIG

  const currentPresetId = styleEnvelope.preset_id ?? 'default_webinar_ebook_v1'

  const presetOptions = STYLE_PRESETS.map(preset => ({
    value: preset.id,
    label: preset.label,
  }))

  const handlePresetChange = (presetId: string) => {
    dispatch({ type: 'SET_STYLE_PRESET', payload: presetId })
    setShowCustomize(false)
  }

  const handleStyleChange = (updates: Partial<StyleConfig>) => {
    dispatch({ type: 'UPDATE_STYLE_CONFIG', payload: updates })
  }

  const handleDraftChange = (value: string) => {
    dispatch({ type: 'UPDATE_DRAFT', payload: value })
  }

  const handleGenerateDraft = () => {
    dispatch({ type: 'GENERATE_SAMPLE_DRAFT' })
  }

  const currentPreset = STYLE_PRESETS.find(p => p.id === currentPresetId)

  return (
    <div className="space-y-6">
      <Card title="Style Configuration">
        <p className="text-sm text-gray-500 mb-4">
          Select a preset or customize the style settings for your ebook generation.
        </p>

        <div className="space-y-4">
          <Select
            label="Style Preset"
            value={currentPresetId}
            onChange={handlePresetChange}
            options={presetOptions}
          />

          {currentPreset && (
            <p className="text-sm text-gray-600 italic">
              {currentPreset.description}
            </p>
          )}

          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => setShowCustomize(!showCustomize)}
              className="text-sm text-blue-600 hover:text-blue-800 underline"
            >
              {showCustomize ? 'Hide customization' : 'Customize style settings'}
            </button>
          </div>

          {showCustomize && (
            <div className="mt-4 pt-4 border-t border-gray-200">
              <p className="text-sm text-gray-500 mb-3">
                Adjust individual settings to override the preset defaults:
              </p>
              <StyleControls
                config={styleEnvelope.style}
                onChange={handleStyleChange}
              />
            </div>
          )}
        </div>
      </Card>

      <Card title="Draft Content">
        <DraftEditor
          value={project.draftText}
          onChange={handleDraftChange}
          onGenerate={handleGenerateDraft}
        />
      </Card>
    </div>
  )
}
