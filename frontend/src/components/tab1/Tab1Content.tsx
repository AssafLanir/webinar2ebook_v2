import { useProject } from '../../context/ProjectContext'
import { Card } from '../common/Card'
import { Button } from '../common/Button'
import { TranscriptEditor } from './TranscriptEditor'
import { OutlineEditor } from './OutlineEditor'
import { ResourceList } from './ResourceList'
import { AIAssistSection } from './AIAssistSection'
import { AIPreviewModal } from './AIPreviewModal'

export function Tab1Content() {
  const { state, dispatch, uploadResourceFile, removeResourceFile } = useProject()
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

  const handleFileUpload = async (file: File) => {
    await uploadResourceFile(file)
  }

  const handleFileRemove = async (fileId: string) => {
    // Find the resource with this fileId to get its id
    const resource = project.resources.find(r => r.fileId === fileId)
    if (resource) {
      await removeResourceFile(resource.id, fileId)
    }
  }

  const handleFillSampleData = () => {
    dispatch({ type: 'FILL_SAMPLE_DATA' })
  }

  return (
    <div className="space-y-6">
      {/* Action buttons row */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <AIAssistSection />
        <Button variant="secondary" onClick={handleFillSampleData}>
          Fill with Sample Data
        </Button>
      </div>

      {/* AI Preview Modal */}
      <AIPreviewModal />

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
          projectId={project.id}
          onAdd={handleAddResource}
          onUpdate={handleUpdateResource}
          onRemove={handleRemoveResource}
          onFileUpload={handleFileUpload}
          onFileRemove={handleFileRemove}
        />
      </Card>
    </div>
  )
}
