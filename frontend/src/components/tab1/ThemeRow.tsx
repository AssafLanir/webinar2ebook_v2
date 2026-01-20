import { useState, useRef, useEffect } from 'react'
import type { Theme } from '../../types/edition'
import { COVERAGE_COLORS, COVERAGE_LABELS } from '../../types/edition'

interface ThemeRowProps {
  theme: Theme
  onUpdate: (updates: Partial<Theme>) => void
  onRemove: () => void
  onMoveUp?: () => void
  onMoveDown?: () => void
  isFirst?: boolean
  isLast?: boolean
}

export function ThemeRow({ theme, onUpdate, onRemove, onMoveUp, onMoveDown, isFirst, isLast }: ThemeRowProps) {
  const [isEditingTitle, setIsEditingTitle] = useState(false)
  const [isEditingOneLiner, setIsEditingOneLiner] = useState(false)
  const [editTitle, setEditTitle] = useState(theme.title)
  const [editOneLiner, setEditOneLiner] = useState(theme.one_liner)
  const titleInputRef = useRef<HTMLInputElement>(null)
  const oneLinerInputRef = useRef<HTMLInputElement>(null)

  // Focus input when editing starts
  useEffect(() => {
    if (isEditingTitle && titleInputRef.current) {
      titleInputRef.current.focus()
      titleInputRef.current.select()
    }
  }, [isEditingTitle])

  useEffect(() => {
    if (isEditingOneLiner && oneLinerInputRef.current) {
      oneLinerInputRef.current.focus()
      oneLinerInputRef.current.select()
    }
  }, [isEditingOneLiner])

  const handleTitleSave = () => {
    const trimmed = editTitle.trim()
    if (trimmed && trimmed !== theme.title) {
      onUpdate({ title: trimmed })
    } else {
      setEditTitle(theme.title) // Reset if empty or unchanged
    }
    setIsEditingTitle(false)
  }

  const handleOneLinerSave = () => {
    const trimmed = editOneLiner.trim()
    if (trimmed !== theme.one_liner) {
      onUpdate({ one_liner: trimmed })
    }
    setIsEditingOneLiner(false)
  }

  const handleTitleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      handleTitleSave()
    } else if (e.key === 'Escape') {
      setEditTitle(theme.title)
      setIsEditingTitle(false)
    }
  }

  const handleOneLinerKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      handleOneLinerSave()
    } else if (e.key === 'Escape') {
      setEditOneLiner(theme.one_liner)
      setIsEditingOneLiner(false)
    }
  }

  const handleToggleInclude = () => {
    onUpdate({ include_in_generation: !theme.include_in_generation })
  }

  return (
    <div className={`flex items-start gap-3 p-3 bg-white border rounded-lg group ${!theme.include_in_generation ? 'opacity-50' : ''}`}>
      {/* Include checkbox */}
      <div className="pt-0.5">
        <input
          type="checkbox"
          checked={theme.include_in_generation}
          onChange={handleToggleInclude}
          className="w-4 h-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
          title={theme.include_in_generation ? 'Click to exclude from generation' : 'Click to include in generation'}
        />
      </div>

      {/* Reorder buttons */}
      <div className="flex flex-col gap-0.5">
        <button
          onClick={onMoveUp}
          disabled={isFirst}
          className={`p-0.5 rounded ${isFirst ? 'text-gray-300 cursor-not-allowed' : 'text-gray-400 hover:text-gray-600 hover:bg-gray-100'}`}
          title="Move up"
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 15l7-7 7 7" />
          </svg>
        </button>
        <button
          onClick={onMoveDown}
          disabled={isLast}
          className={`p-0.5 rounded ${isLast ? 'text-gray-300 cursor-not-allowed' : 'text-gray-400 hover:text-gray-600 hover:bg-gray-100'}`}
          title="Move down"
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
          </svg>
        </button>
      </div>

      {/* Content */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          {isEditingTitle ? (
            <input
              ref={titleInputRef}
              type="text"
              value={editTitle}
              onChange={(e) => setEditTitle(e.target.value)}
              onBlur={handleTitleSave}
              onKeyDown={handleTitleKeyDown}
              className="flex-1 font-medium text-gray-900 px-1 py-0.5 border border-blue-400 rounded focus:outline-none focus:ring-1 focus:ring-blue-500"
            />
          ) : (
            <h4
              className="font-medium text-gray-900 truncate cursor-pointer hover:text-blue-600"
              onClick={() => setIsEditingTitle(true)}
              title="Click to edit title"
            >
              {theme.title}
            </h4>
          )}
          <span className={`px-2 py-0.5 text-xs font-medium rounded ${COVERAGE_COLORS[theme.coverage]}`}>
            {COVERAGE_LABELS[theme.coverage]}
          </span>
        </div>

        {isEditingOneLiner ? (
          <input
            ref={oneLinerInputRef}
            type="text"
            value={editOneLiner}
            onChange={(e) => setEditOneLiner(e.target.value)}
            onBlur={handleOneLinerSave}
            onKeyDown={handleOneLinerKeyDown}
            className="w-full text-sm text-gray-500 px-1 py-0.5 border border-blue-400 rounded focus:outline-none focus:ring-1 focus:ring-blue-500 mt-1"
          />
        ) : (
          <p
            className="text-sm text-gray-500 truncate cursor-pointer hover:text-blue-600"
            onClick={() => setIsEditingOneLiner(true)}
            title="Click to edit description"
          >
            {theme.one_liner || '(click to add description)'}
          </p>
        )}

        {theme.coverage === 'weak' && (
          <p className="text-xs text-red-600 mt-1 flex items-center gap-1">
            <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
              <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
            </svg>
            Limited source material
          </p>
        )}

        {theme.supporting_segments.length > 0 && (
          <details className="mt-2">
            <summary className="text-xs text-gray-400 cursor-pointer hover:text-gray-600">
              {theme.supporting_segments.length} supporting segments
            </summary>
            <div className="mt-1 space-y-1">
              {theme.supporting_segments.slice(0, 3).map((seg, i) => (
                <p key={i} className="text-xs text-gray-500 truncate pl-2 border-l-2 border-gray-200">
                  {seg.text_preview}
                </p>
              ))}
            </div>
          </details>
        )}
      </div>

      {/* Actions */}
      <button
        onClick={onRemove}
        className="opacity-0 group-hover:opacity-100 p-1 text-gray-400 hover:text-red-500"
        title="Remove theme"
      >
        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
        </svg>
      </button>
    </div>
  )
}
