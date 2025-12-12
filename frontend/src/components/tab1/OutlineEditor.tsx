import { useState } from 'react'
import {
  DndContext,
  closestCenter,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
} from '@dnd-kit/core'
import type { DragEndEvent } from '@dnd-kit/core'
import {
  SortableContext,
  sortableKeyboardCoordinates,
  verticalListSortingStrategy,
} from '@dnd-kit/sortable'
import type { OutlineItem as OutlineItemType } from '../../types/project'
import { OutlineItem } from './OutlineItem'
import { Button } from '../common/Button'
import { Input } from '../common/Input'

export interface OutlineEditorProps {
  items: OutlineItemType[]
  onAdd: (title: string, level?: number) => void
  onUpdate: (id: string, updates: Partial<OutlineItemType>) => void
  onRemove: (id: string) => void
  onReorder: (orderedIds: string[]) => void
}

export function OutlineEditor({ items, onAdd, onUpdate, onRemove, onReorder }: OutlineEditorProps) {
  const [newItemTitle, setNewItemTitle] = useState('')

  const sensors = useSensors(
    useSensor(PointerSensor),
    useSensor(KeyboardSensor, {
      coordinateGetter: sortableKeyboardCoordinates,
    })
  )

  const handleDragEnd = (event: DragEndEvent) => {
    const { active, over } = event

    if (over && active.id !== over.id) {
      const oldIndex = items.findIndex(item => item.id === active.id)
      const newIndex = items.findIndex(item => item.id === over.id)

      const newOrder = [...items]
      const [movedItem] = newOrder.splice(oldIndex, 1)
      newOrder.splice(newIndex, 0, movedItem)

      onReorder(newOrder.map(item => item.id))
    }
  }

  const handleAddItem = () => {
    if (newItemTitle.trim()) {
      onAdd(newItemTitle.trim())
      setNewItemTitle('')
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      e.preventDefault()
      handleAddItem()
    }
  }

  const sortedItems = [...items].sort((a, b) => a.order - b.order)

  return (
    <div>
      <label className="block text-sm font-medium text-slate-300 mb-2">Outline</label>

      {/* Add new item */}
      <div className="flex gap-2 mb-4">
        <div className="flex-1">
          <Input
            value={newItemTitle}
            onChange={setNewItemTitle}
            placeholder="Add new chapter or section..."
            onKeyDown={handleKeyDown}
          />
        </div>
        <Button onClick={handleAddItem} disabled={!newItemTitle.trim()}>
          Add
        </Button>
      </div>

      {/* Sortable list */}
      {sortedItems.length === 0 ? (
        <p className="text-slate-400 text-sm italic py-4">
          No outline items yet. Add chapters and sections above.
        </p>
      ) : (
        <DndContext
          sensors={sensors}
          collisionDetection={closestCenter}
          onDragEnd={handleDragEnd}
        >
          <SortableContext items={sortedItems.map(i => i.id)} strategy={verticalListSortingStrategy}>
            <div className="space-y-2">
              {sortedItems.map(item => (
                <OutlineItem
                  key={item.id}
                  item={item}
                  onUpdate={updates => onUpdate(item.id, updates)}
                  onRemove={() => onRemove(item.id)}
                />
              ))}
            </div>
          </SortableContext>
        </DndContext>
      )}
    </div>
  )
}
