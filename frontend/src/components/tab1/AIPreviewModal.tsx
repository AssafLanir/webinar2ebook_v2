/**
 * AIPreviewModal - Modal for previewing AI-generated content before applying
 *
 * Supports:
 * - Clean transcript preview (text with copy button)
 * - Outline suggestions (checkboxes - future)
 * - Resource suggestions (checkboxes - future)
 */

import { useState } from 'react'
import { useProject } from '../../context/ProjectContext'
import { Button } from '../common/Button'

export function AIPreviewModal() {
  const { state, dispatch } = useProject()
  const { aiPreview } = state
  const [copied, setCopied] = useState(false)

  if (!aiPreview.isOpen || !aiPreview.preview) {
    return null
  }

  const preview = aiPreview.preview

  const handleApply = () => {
    dispatch({ type: 'APPLY_AI_PREVIEW' })
  }

  const handleDiscard = () => {
    dispatch({ type: 'DISCARD_AI_PREVIEW' })
  }

  const handleCopyToClipboard = async () => {
    if (preview.type !== 'clean-transcript') return

    try {
      await navigator.clipboard.writeText(preview.cleanedTranscript)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch (err) {
      console.error('Failed to copy to clipboard:', err)
    }
  }

  const handleBackdropClick = (e: React.MouseEvent) => {
    if (e.target === e.currentTarget) {
      handleDiscard()
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm"
      onClick={handleBackdropClick}
    >
      <div className="bg-slate-800 rounded-xl shadow-2xl border border-slate-700 w-full max-w-3xl max-h-[80vh] flex flex-col mx-4">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-700">
          <h2 className="text-xl font-semibold text-white">
            {preview.type === 'clean-transcript' && 'Cleaned Transcript Preview'}
            {preview.type === 'suggest-outline' && 'Suggested Outline'}
            {preview.type === 'suggest-resources' && 'Suggested Resources'}
          </h2>
          <button
            onClick={handleDiscard}
            className="text-slate-400 hover:text-white transition-colors"
            aria-label="Close"
          >
            <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6">
          {preview.type === 'clean-transcript' && (
            <CleanTranscriptPreview
              text={preview.cleanedTranscript}
              onCopy={handleCopyToClipboard}
              copied={copied}
            />
          )}
          {preview.type === 'suggest-outline' && (
            <OutlinePreview
              items={preview.items}
              selected={preview.selected}
              onToggle={(index) => dispatch({ type: 'TOGGLE_AI_PREVIEW_SELECTION', payload: index })}
            />
          )}
          {preview.type === 'suggest-resources' && (
            <ResourcesPreview
              resources={preview.resources}
              selected={preview.selected}
              onToggle={(index) => dispatch({ type: 'TOGGLE_AI_PREVIEW_SELECTION', payload: index })}
            />
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end gap-3 px-6 py-4 border-t border-slate-700">
          <Button variant="ghost" onClick={handleDiscard}>
            Discard
          </Button>
          <Button variant="primary" onClick={handleApply}>
            {preview.type === 'clean-transcript' && 'Apply Changes'}
            {preview.type === 'suggest-outline' && 'Insert Selected'}
            {preview.type === 'suggest-resources' && 'Add Selected'}
          </Button>
        </div>
      </div>
    </div>
  )
}

// Clean transcript preview with copy button
interface CleanTranscriptPreviewProps {
  text: string
  onCopy: () => void
  copied: boolean
}

function CleanTranscriptPreview({ text, onCopy, copied }: CleanTranscriptPreviewProps) {
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-sm text-slate-400">
          Review the cleaned transcript below. Click "Apply Changes" to replace your current transcript.
        </p>
        <button
          onClick={onCopy}
          className="flex items-center gap-1.5 px-3 py-1.5 text-sm rounded-lg bg-slate-700 text-slate-300 hover:bg-slate-600 transition-colors"
        >
          {copied ? (
            <>
              <CheckIcon />
              Copied!
            </>
          ) : (
            <>
              <CopyIcon />
              Copy
            </>
          )}
        </button>
      </div>
      <div className="bg-slate-900 rounded-lg p-4 max-h-96 overflow-y-auto">
        <pre className="whitespace-pre-wrap text-slate-200 text-sm font-mono leading-relaxed">
          {text}
        </pre>
      </div>
    </div>
  )
}

// Outline preview with checkboxes (for future use)
interface OutlinePreviewProps {
  items: Array<{ title: string; level: number; notes?: string }>
  selected: Set<number>
  onToggle: (index: number) => void
}

function OutlinePreview({ items, selected, onToggle }: OutlinePreviewProps) {
  const allSelected = items.length > 0 && selected.size === items.length

  const handleSelectAll = () => {
    if (allSelected) {
      // Deselect all
      items.forEach((_, index) => {
        if (selected.has(index)) onToggle(index)
      })
    } else {
      // Select all
      items.forEach((_, index) => {
        if (!selected.has(index)) onToggle(index)
      })
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-sm text-slate-400">
          Select the outline items you want to add. They will be appended to your existing outline.
        </p>
        <button
          onClick={handleSelectAll}
          className="text-sm text-cyan-400 hover:text-cyan-300"
        >
          {allSelected ? 'Deselect all' : 'Select all'}
        </button>
      </div>
      <div className="space-y-2">
        {items.map((item, index) => (
          <label
            key={index}
            className={`flex items-start gap-3 p-3 rounded-lg cursor-pointer transition-colors ${
              selected.has(index)
                ? 'bg-cyan-500/10 border border-cyan-500/30'
                : 'bg-slate-700/50 border border-transparent hover:bg-slate-700'
            }`}
          >
            <input
              type="checkbox"
              checked={selected.has(index)}
              onChange={() => onToggle(index)}
              className="mt-1 w-4 h-4 rounded border-slate-500 text-cyan-500 focus:ring-cyan-500 focus:ring-offset-slate-800"
            />
            <div className="flex-1">
              <div className="flex items-center gap-2">
                <span className="text-xs text-slate-500 font-mono">L{item.level}</span>
                <span className="text-slate-200">{item.title}</span>
              </div>
              {item.notes && (
                <p className="mt-1 text-sm text-slate-400">{item.notes}</p>
              )}
            </div>
          </label>
        ))}
      </div>
      <p className="text-sm text-slate-500">
        {selected.size} of {items.length} items selected
      </p>
    </div>
  )
}

// Resources preview with checkboxes (for future use)
interface ResourcesPreviewProps {
  resources: Array<{ label: string; url_or_note: string }>
  selected: Set<number>
  onToggle: (index: number) => void
}

function ResourcesPreview({ resources, selected, onToggle }: ResourcesPreviewProps) {
  const allSelected = resources.length > 0 && selected.size === resources.length

  const handleSelectAll = () => {
    if (allSelected) {
      resources.forEach((_, index) => {
        if (selected.has(index)) onToggle(index)
      })
    } else {
      resources.forEach((_, index) => {
        if (!selected.has(index)) onToggle(index)
      })
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-sm text-slate-400">
          Select the resources you want to add. They will be appended to your existing resources.
        </p>
        <button
          onClick={handleSelectAll}
          className="text-sm text-cyan-400 hover:text-cyan-300"
        >
          {allSelected ? 'Deselect all' : 'Select all'}
        </button>
      </div>
      <div className="space-y-2">
        {resources.map((resource, index) => (
          <label
            key={index}
            className={`flex items-start gap-3 p-3 rounded-lg cursor-pointer transition-colors ${
              selected.has(index)
                ? 'bg-cyan-500/10 border border-cyan-500/30'
                : 'bg-slate-700/50 border border-transparent hover:bg-slate-700'
            }`}
          >
            <input
              type="checkbox"
              checked={selected.has(index)}
              onChange={() => onToggle(index)}
              className="mt-1 w-4 h-4 rounded border-slate-500 text-cyan-500 focus:ring-cyan-500 focus:ring-offset-slate-800"
            />
            <div className="flex-1">
              <span className="text-slate-200 font-medium">{resource.label}</span>
              <p className="mt-1 text-sm text-slate-400 break-all">{resource.url_or_note}</p>
            </div>
          </label>
        ))}
      </div>
      <p className="text-sm text-slate-500">
        {selected.size} of {resources.length} resources selected
      </p>
    </div>
  )
}

// Icons
function CopyIcon() {
  return (
    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
    </svg>
  )
}

function CheckIcon() {
  return (
    <svg className="w-4 h-4 text-green-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
    </svg>
  )
}
