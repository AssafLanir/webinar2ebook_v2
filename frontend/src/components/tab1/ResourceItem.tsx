import type { Resource } from '../../types/project'
import { Button } from '../common/Button'

export interface ResourceItemProps {
  resource: Resource
  onUpdate: (updates: Partial<Resource>) => void
  onRemove: () => void
}

export function ResourceItem({ resource, onUpdate, onRemove }: ResourceItemProps) {
  return (
    <div className="flex items-start gap-3 p-3 bg-slate-700/50 border border-slate-600 rounded-lg">
      <div className="flex-1 space-y-2">
        <input
          type="text"
          value={resource.label}
          onChange={e => onUpdate({ label: e.target.value })}
          className="w-full bg-transparent border-none outline-none focus:ring-0 text-white font-medium placeholder-slate-400"
          placeholder="Resource title..."
        />
        <input
          type="text"
          value={resource.urlOrNote}
          onChange={e => onUpdate({ urlOrNote: e.target.value })}
          className="w-full bg-transparent border-none outline-none focus:ring-0 text-slate-400 text-sm placeholder-slate-500"
          placeholder="URL or note..."
        />
      </div>
      <Button variant="ghost" size="sm" onClick={onRemove}>
        <svg className="w-4 h-4 text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
        </svg>
      </Button>
    </div>
  )
}
