import { Textarea } from '../common/Textarea'
import { Button } from '../common/Button'

export interface DraftEditorProps {
  value: string
  onChange: (value: string) => void
  onGenerate: () => void
}

export function DraftEditor({ value, onChange, onGenerate }: DraftEditorProps) {
  const wordCount = value.trim() ? value.trim().split(/\s+/).length : 0

  return (
    <div>
      <div className="flex justify-between items-center mb-4">
        <Button variant="secondary" onClick={onGenerate}>
          <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M13 10V3L4 14h7v7l9-11h-7z"
            />
          </svg>
          Generate Sample Draft
        </Button>
        <span className="text-sm text-gray-500">{wordCount} words</span>
      </div>

      <Textarea
        value={value}
        onChange={onChange}
        placeholder="Your draft content will appear here. Click 'Generate Sample Draft' to see an example, or start writing your own content..."
        rows={20}
      />

      <p className="text-sm text-gray-500 mt-2">
        Tip: The draft will be included in your final ebook export. You can edit it at any time.
      </p>
    </div>
  )
}
