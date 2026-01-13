import { useState } from 'react'
import { useProject } from '../../context/ProjectContext'
import { Card } from '../common/Card'
import { Button } from '../common/Button'
import { TranscriptEditor } from './TranscriptEditor'
import { OutlineEditor } from './OutlineEditor'
import { ResourceList } from './ResourceList'
import { AIAssistSection } from './AIAssistSection'
import { AIPreviewModal } from './AIPreviewModal'
import { EditionSelector } from './EditionSelector'
import { ThemesPanel } from './ThemesPanel'
import { pollThemeProposal } from '../../services/themeApi'
import type { Edition, Theme } from '../../types/edition'

export function Tab1Content() {
  const { state, dispatch, uploadResourceFile, removeResourceFile } = useProject()
  const { project } = state
  const [isProposingThemes, setIsProposingThemes] = useState(false)
  const [themeError, setThemeError] = useState<string | null>(null)

  if (!project) return null

  const handleEditionChange = (edition: Edition) => {
    dispatch({ type: 'SET_EDITION', payload: edition })
  }

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

  // Theme handlers (Ideas Edition)
  const handleProposeThemes = async () => {
    if (!project) return

    setIsProposingThemes(true)
    setThemeError(null)
    try {
      const themes = await pollThemeProposal(project.id)
      dispatch({ type: 'SET_THEMES', payload: themes })
    } catch (err) {
      console.error('Theme proposal failed:', err)
      setThemeError(err instanceof Error ? err.message : 'Theme proposal failed')
    } finally {
      setIsProposingThemes(false)
    }
  }

  const handleUpdateTheme = (id: string, updates: Partial<Theme>) => {
    dispatch({ type: 'UPDATE_THEME', payload: { id, updates } })
  }

  const handleRemoveTheme = (id: string) => {
    dispatch({ type: 'REMOVE_THEME', payload: id })
  }

  const handleReorderThemes = (orderedIds: string[]) => {
    dispatch({ type: 'REORDER_THEMES', payload: orderedIds })
  }

  const isIdeasEdition = project.edition === 'ideas'

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

      {/* Edition Selector */}
      <Card title="Output Format">
        <EditionSelector
          value={project.edition}
          onChange={handleEditionChange}
          recommendedEdition="qa"
        />
      </Card>

      {/* Transcript */}
      <Card title="Transcript">
        <TranscriptEditor value={project.transcriptText} onChange={handleTranscriptChange} />
      </Card>

      {/* Conditional: Outline (Q&A) or Themes (Ideas) */}
      {isIdeasEdition ? (
        <Card title="Themes">
          {themeError && (
            <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg">
              <p className="text-sm text-red-600">{themeError}</p>
            </div>
          )}
          <ThemesPanel
            themes={project.themes}
            onProposeThemes={handleProposeThemes}
            onUpdateTheme={handleUpdateTheme}
            onRemoveTheme={handleRemoveTheme}
            onReorderThemes={handleReorderThemes}
            isProposing={isProposingThemes}
          />
        </Card>
      ) : (
        <Card title="Outline">
          <p className="text-sm text-gray-500 mb-4">
            Optional: Used for topic grouping only. Won't change the interview content.
          </p>
          <OutlineEditor
            items={project.outlineItems}
            onAdd={handleAddOutlineItem}
            onUpdate={handleUpdateOutlineItem}
            onRemove={handleRemoveOutlineItem}
            onReorder={handleReorderOutlineItems}
          />
        </Card>
      )}

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
