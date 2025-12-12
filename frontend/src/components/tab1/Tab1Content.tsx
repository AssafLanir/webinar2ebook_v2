import { useProject } from '../../context/ProjectContext'
import { Card } from '../common/Card'
import { Button } from '../common/Button'
import { TranscriptEditor } from './TranscriptEditor'
import { OutlineEditor } from './OutlineEditor'
import { ResourceList } from './ResourceList'

export function Tab1Content() {
  const { state, dispatch } = useProject()
  const { project } = state

  if (!project) return null

  const handleTranscriptChange = (value: string) => {
    dispatch({ type: 'UPDATE_TRANSCRIPT', payload: value })
  }

  const handleAddOutlineItem = (title: string, level?: number) => {
    dispatch({ type: 'ADD_OUTLINE_ITEM', payload: { title, level } })
  }

  const handleUpdateOutlineItem = (id: string, updates: Partial<{ title: string; level: number }>) => {
    dispatch({ type: 'UPDATE_OUTLINE_ITEM', payload: { id, updates } })
  }

  const handleRemoveOutlineItem = (id: string) => {
    dispatch({ type: 'REMOVE_OUTLINE_ITEM', payload: id })
  }

  const handleReorderOutlineItems = (orderedIds: string[]) => {
    dispatch({ type: 'REORDER_OUTLINE_ITEMS', payload: orderedIds })
  }

  const handleAddResource = (label: string, urlOrNote?: string) => {
    dispatch({ type: 'ADD_RESOURCE', payload: { label, urlOrNote } })
  }

  const handleUpdateResource = (id: string, updates: Partial<{ label: string; urlOrNote: string }>) => {
    dispatch({ type: 'UPDATE_RESOURCE', payload: { id, updates } })
  }

  const handleRemoveResource = (id: string) => {
    dispatch({ type: 'REMOVE_RESOURCE', payload: id })
  }

  const handleFillSampleData = () => {
    dispatch({ type: 'FILL_SAMPLE_DATA' })
  }

  return (
    <div className="space-y-6">
      {/* Fill Sample Data Button */}
      <div className="flex justify-end">
        <Button variant="secondary" onClick={handleFillSampleData}>
          Fill with Sample Data
        </Button>
      </div>

      {/* Transcript */}
      <Card title="Transcript">
        <TranscriptEditor value={project.transcriptText} onChange={handleTranscriptChange} />
      </Card>

      {/* Outline */}
      <Card title="Outline">
        <OutlineEditor
          items={project.outlineItems}
          onAdd={handleAddOutlineItem}
          onUpdate={handleUpdateOutlineItem}
          onRemove={handleRemoveOutlineItem}
          onReorder={handleReorderOutlineItems}
        />
      </Card>

      {/* Resources */}
      <Card title="Resources">
        <ResourceList
          resources={project.resources}
          onAdd={handleAddResource}
          onUpdate={handleUpdateResource}
          onRemove={handleRemoveResource}
        />
      </Card>
    </div>
  )
}
