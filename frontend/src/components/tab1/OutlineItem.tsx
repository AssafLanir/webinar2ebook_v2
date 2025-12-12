import { useSortable } from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'
import type { OutlineItem as OutlineItemType } from '../../types/project'
import { Button } from '../common/Button'

export interface OutlineItemProps {
  item: OutlineItemType
  onUpdate: (updates: Partial<OutlineItemType>) => void
  onRemove: () => void
}

export function OutlineItem({ item, onUpdate, onRemove }: OutlineItemProps) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({
    id: item.id,
  })

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
  }

  const levelIndent = (item.level - 1) * 24

  return (
    <div
      ref={setNodeRef}
      style={style}
      className={`
        flex items-center gap-3 p-3 bg-slate-700/50 border border-slate-600 rounded-lg
        ${isDragging ? 'opacity-50 shadow-lg' : ''}
      `}
    >
      {/* Drag Handle */}
      <button
        {...attributes}
        {...listeners}
        className="cursor-grab active:cursor-grabbing text-slate-400 hover:text-slate-200"
        aria-label="Drag to reorder"
      >
        <svg
          className="w-5 h-5"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M4 8h16M4 16h16"
          />
        </svg>
      </button>

      {/* Level Indicator & Title */}
      <div className="flex-1 flex items-center" style={{ marginLeft: levelIndent }}>
        <span className="text-xs text-slate-500 mr-2 font-mono">L{item.level}</span>
        <input
          type="text"
          value={item.title}
          onChange={e => onUpdate({ title: e.target.value })}
          className="flex-1 bg-transparent border-none outline-none focus:ring-0 text-white placeholder-slate-400"
          placeholder="Chapter title..."
        />
      </div>

      {/* Level Controls */}
      <div className="flex items-center gap-1">
        <button
          onClick={() => onUpdate({ level: Math.max(1, item.level - 1) })}
          disabled={item.level <= 1}
          className="p-1 text-slate-400 hover:text-slate-200 disabled:opacity-30 disabled:cursor-not-allowed"
          title="Decrease level"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
          </svg>
        </button>
        <button
          onClick={() => onUpdate({ level: Math.min(3, item.level + 1) })}
          disabled={item.level >= 3}
          className="p-1 text-slate-400 hover:text-slate-200 disabled:opacity-30 disabled:cursor-not-allowed"
          title="Increase level"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
          </svg>
        </button>
      </div>

      {/* Remove Button */}
      <Button variant="ghost" size="sm" onClick={onRemove}>
        <svg className="w-4 h-4 text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
        </svg>
      </Button>
    </div>
  )
}
