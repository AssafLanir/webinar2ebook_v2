import { useProject } from '../../context/ProjectContext'
import { Card } from '../common/Card'
import { VisualGallery } from './VisualGallery'
import { AddCustomVisual } from './AddCustomVisual'

export function Tab2Content() {
  const { state, dispatch } = useProject()
  const { project } = state

  if (!project) return null

  const handleToggleSelection = (id: string) => {
    dispatch({ type: 'TOGGLE_VISUAL_SELECTION', payload: id })
  }

  const handleAddCustomVisual = (title: string, description: string) => {
    dispatch({ type: 'ADD_CUSTOM_VISUAL', payload: { title, description } })
  }

  return (
    <div className="space-y-6">
      <Card title="Visual Gallery">
        <VisualGallery
          visuals={project.visuals}
          onToggleSelection={handleToggleSelection}
        />
      </Card>

      <Card title="Custom Visuals">
        <p className="text-sm text-gray-500 mb-4">
          Add your own visuals to include in the ebook. Custom visuals are automatically selected.
        </p>
        <AddCustomVisual onAdd={handleAddCustomVisual} />
      </Card>
    </div>
  )
}
