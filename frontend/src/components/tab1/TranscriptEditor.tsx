import { Textarea } from '../common/Textarea'

export interface TranscriptEditorProps {
  value: string
  onChange: (value: string) => void
}

export function TranscriptEditor({ value, onChange }: TranscriptEditorProps) {
  return (
    <div>
      <Textarea
        label="Transcript"
        value={value}
        onChange={onChange}
        placeholder="Paste or type your webinar transcript here..."
        rows={12}
        className="max-h-96 overflow-y-auto"
      />
    </div>
  )
}
