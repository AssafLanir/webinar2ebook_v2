import { useState } from 'react'
import type { Resource } from '../../types/project'
import { ResourceItem } from './ResourceItem'
import { Button } from '../common/Button'
import { Input } from '../common/Input'

export interface ResourceListProps {
  resources: Resource[]
  onAdd: (label: string, urlOrNote?: string) => void
  onUpdate: (id: string, updates: Partial<Resource>) => void
  onRemove: (id: string) => void
}

export function ResourceList({ resources, onAdd, onUpdate, onRemove }: ResourceListProps) {
  const [newLabel, setNewLabel] = useState('')
  const [newUrl, setNewUrl] = useState('')

  const handleAdd = () => {
    if (newLabel.trim()) {
      onAdd(newLabel.trim(), newUrl.trim() || undefined)
      setNewLabel('')
      setNewUrl('')
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      e.preventDefault()
      handleAdd()
    }
  }

  const sortedResources = [...resources].sort((a, b) => a.order - b.order)

  return (
    <div>
      <label className="block text-sm font-medium text-slate-300 mb-2">Resources</label>

      {/* Add new resource */}
      <div className="flex gap-2 mb-4">
        <div className="flex-1">
          <Input
            value={newLabel}
            onChange={setNewLabel}
            placeholder="Resource name..."
            onKeyDown={handleKeyDown}
          />
        </div>
        <div className="flex-1">
          <Input
            value={newUrl}
            onChange={setNewUrl}
            placeholder="URL or note (optional)..."
            onKeyDown={handleKeyDown}
          />
        </div>
        <Button onClick={handleAdd} disabled={!newLabel.trim()}>
          Add
        </Button>
      </div>

      {/* Resource list */}
      {sortedResources.length === 0 ? (
        <p className="text-slate-400 text-sm italic py-4">
          No resources yet. Add links, references, or notes above.
        </p>
      ) : (
        <div className="space-y-2">
          {sortedResources.map(resource => (
            <ResourceItem
              key={resource.id}
              resource={resource}
              onUpdate={updates => onUpdate(resource.id, updates)}
              onRemove={() => onRemove(resource.id)}
            />
          ))}
        </div>
      )}
    </div>
  )
}
