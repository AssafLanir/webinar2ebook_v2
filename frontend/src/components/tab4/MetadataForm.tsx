import { Input } from '../common/Input'
import { Textarea } from '../common/Textarea'

export interface MetadataFormProps {
  finalTitle: string
  finalSubtitle: string
  creditsText: string
  onTitleChange: (value: string) => void
  onSubtitleChange: (value: string) => void
  onCreditsChange: (value: string) => void
}

export function MetadataForm({
  finalTitle,
  finalSubtitle,
  creditsText,
  onTitleChange,
  onSubtitleChange,
  onCreditsChange,
}: MetadataFormProps) {
  return (
    <div className="space-y-4">
      <Input
        label="Final Title"
        value={finalTitle}
        onChange={onTitleChange}
        placeholder="Enter the final ebook title..."
      />

      <Input
        label="Subtitle"
        value={finalSubtitle}
        onChange={onSubtitleChange}
        placeholder="Enter a subtitle (optional)..."
      />

      <Textarea
        label="Credits"
        value={creditsText}
        onChange={onCreditsChange}
        placeholder="Enter credits, acknowledgments, or author information..."
        rows={3}
      />
    </div>
  )
}
