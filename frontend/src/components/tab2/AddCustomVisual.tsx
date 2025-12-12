import { useState } from 'react'
import { Button } from '../common/Button'
import { Input } from '../common/Input'
import { Textarea } from '../common/Textarea'

export interface AddCustomVisualProps {
  onAdd: (title: string, description: string) => void
}

export function AddCustomVisual({ onAdd }: AddCustomVisualProps) {
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [isExpanded, setIsExpanded] = useState(false)

  const handleSubmit = () => {
    if (title.trim() && description.trim()) {
      onAdd(title.trim(), description.trim())
      setTitle('')
      setDescription('')
      setIsExpanded(false)
    }
  }

  const handleCancel = () => {
    setTitle('')
    setDescription('')
    setIsExpanded(false)
  }

  const isValid = title.trim().length > 0 && description.trim().length > 0

  if (!isExpanded) {
    return (
      <Button variant="secondary" onClick={() => setIsExpanded(true)}>
        <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
        </svg>
        Add Custom Visual
      </Button>
    )
  }

  return (
    <div className="bg-gray-50 border border-gray-200 rounded-lg p-4">
      <h4 className="font-medium text-gray-900 mb-4">Add Custom Visual</h4>

      <div className="space-y-4">
        <Input
          label="Title"
          value={title}
          onChange={setTitle}
          placeholder="e.g., Team Photo, Product Screenshot"
        />

        <Textarea
          label="Description"
          value={description}
          onChange={setDescription}
          placeholder="Describe what this visual shows..."
          rows={3}
        />

        <div className="flex gap-2 justify-end">
          <Button variant="ghost" onClick={handleCancel}>
            Cancel
          </Button>
          <Button onClick={handleSubmit} disabled={!isValid}>
            Add Visual
          </Button>
        </div>
      </div>
    </div>
  )
}
