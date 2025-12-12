import { useProject } from '../../context/ProjectContext'
import { Card } from '../common/Card'
import { StyleControls } from './StyleControls'
import { DraftEditor } from './DraftEditor'
import type { StyleConfig } from '../../types/project'

export function Tab3Content() {
  const { state, dispatch } = useProject()
  const { project } = state

  if (!project) return null

  const handleStyleChange = (updates: Partial<StyleConfig>) => {
    dispatch({ type: 'UPDATE_STYLE_CONFIG', payload: updates })
  }

  const handleDraftChange = (value: string) => {
    dispatch({ type: 'UPDATE_DRAFT', payload: value })
  }

  const handleGenerateDraft = () => {
    dispatch({ type: 'GENERATE_SAMPLE_DRAFT' })
  }

  return (
    <div className="space-y-6">
      <Card title="Style Configuration">
        <p className="text-sm text-gray-500 mb-4">
          Configure how your ebook should be written. These settings will guide the content generation.
        </p>
        <StyleControls config={project.styleConfig ?? {}} onChange={handleStyleChange} />
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
