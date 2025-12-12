import { useProject } from '../../context/ProjectContext'
import { Card } from '../common/Card'
import { MetadataForm } from './MetadataForm'
import { StructurePreview } from './StructurePreview'
import { ExportButton } from './ExportButton'
import { downloadMarkdown } from '../../utils/exportHelpers'

export function Tab4Content() {
  const { state, dispatch } = useProject()
  const { project } = state

  if (!project) return null

  const handleTitleChange = (value: string) => {
    dispatch({ type: 'UPDATE_FINAL_TITLE', payload: value })
  }

  const handleSubtitleChange = (value: string) => {
    dispatch({ type: 'UPDATE_FINAL_SUBTITLE', payload: value })
  }

  const handleCreditsChange = (value: string) => {
    dispatch({ type: 'UPDATE_CREDITS', payload: value })
  }

  const handleExport = () => {
    downloadMarkdown(project)
  }

  return (
    <div className="space-y-6">
      <Card title="Final Metadata">
        <p className="text-sm text-gray-500 mb-4">
          Set the final title, subtitle, and credits for your ebook.
        </p>
        <MetadataForm
          finalTitle={project.finalTitle}
          finalSubtitle={project.finalSubtitle}
          creditsText={project.creditsText}
          onTitleChange={handleTitleChange}
          onSubtitleChange={handleSubtitleChange}
          onCreditsChange={handleCreditsChange}
        />
      </Card>

      <Card title="Structure Preview">
        <p className="text-sm text-gray-500 mb-4">
          Preview of what will be included in your exported ebook.
        </p>
        <StructurePreview
          chapters={project.outlineItems}
          visuals={project.visuals}
        />
      </Card>

      <Card title="Export">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-gray-700">
              Ready to export your ebook as a Markdown file.
            </p>
            <p className="text-sm text-gray-500 mt-1">
              The file will include all metadata, chapters, visuals, and content.
            </p>
          </div>
          <ExportButton onExport={handleExport} />
        </div>
      </Card>
    </div>
  )
}
