import { useState } from 'react'
import type { Resource } from '../../types/project'
import { ResourceItem } from './ResourceItem'
import { Button } from '../common/Button'
import { Input } from '../common/Input'
import { FileUploadZone } from '../common/FileUploadZone'

export interface ResourceListProps {
  resources: Resource[]
  projectId: string
  onAdd: (label: string, urlOrNote?: string) => void
  onUpdate: (id: string, updates: Partial<Resource>) => void
  onRemove: (id: string) => void
  onFileUpload?: (file: File) => Promise<void>
  onFileRemove?: (fileId: string) => Promise<void>
}

export function ResourceList({
  resources,
  projectId,
  onAdd,
  onUpdate,
  onRemove,
  onFileUpload,
  onFileRemove,
}: ResourceListProps) {
  const [newLabel, setNewLabel] = useState('')
  const [newUrl, setNewUrl] = useState('')
  const [isUploading, setIsUploading] = useState(false)
  const [uploadError, setUploadError] = useState<string | null>(null)
  const [lastFailedFile, setLastFailedFile] = useState<File | null>(null)

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

  const handleFileSelect = async (file: File) => {
    if (!onFileUpload) return

    setIsUploading(true)
    setUploadError(null)
    setLastFailedFile(null)

    try {
      await onFileUpload(file)
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to upload file'
      setUploadError(message)
      setLastFailedFile(file)
    } finally {
      setIsUploading(false)
    }
  }

  const handleRetryUpload = async () => {
    if (lastFailedFile) {
      await handleFileSelect(lastFailedFile)
    }
  }

  const handleDismissError = () => {
    setUploadError(null)
    setLastFailedFile(null)
  }

  const handleRemove = async (resource: Resource) => {
    // If it's a file resource and we have onFileRemove, use that to also delete from server
    if (resource.resourceType === 'file' && resource.fileId && onFileRemove) {
      try {
        await onFileRemove(resource.fileId)
      } catch (error) {
        console.error('Failed to delete file:', error)
        // Still remove from UI even if server delete fails
      }
    }
    onRemove(resource.id)
  }

  const sortedResources = [...resources].sort((a, b) => a.order - b.order)

  return (
    <div>
      <label className="block text-sm font-medium text-slate-300 mb-2">Resources</label>

      {/* Add new URL/note resource */}
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

      {/* File upload zone */}
      {onFileUpload && (
        <div className="mb-4 space-y-2">
          <FileUploadZone
            onFileSelect={handleFileSelect}
            isUploading={isUploading}
            error={null} // We handle errors separately below
          />

          {/* Upload error with retry/dismiss */}
          {uploadError && (
            <div className="flex items-start gap-3 p-3 bg-red-500/10 border border-red-500/30 rounded-lg">
              <svg
                className="w-5 h-5 text-red-400 flex-shrink-0 mt-0.5"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
                />
              </svg>
              <div className="flex-1 min-w-0">
                <p className="text-sm text-red-400 font-medium">Upload failed</p>
                <p className="text-sm text-red-300/80 mt-0.5">{uploadError}</p>
                {lastFailedFile && (
                  <p className="text-xs text-slate-500 mt-1">File: {lastFailedFile.name}</p>
                )}
              </div>
              <div className="flex items-center gap-2 flex-shrink-0">
                {lastFailedFile && (
                  <button
                    onClick={handleRetryUpload}
                    disabled={isUploading}
                    className="text-sm text-cyan-400 hover:text-cyan-300 font-medium disabled:opacity-50"
                  >
                    Retry
                  </button>
                )}
                <button
                  onClick={handleDismissError}
                  className="text-slate-400 hover:text-slate-300"
                  title="Dismiss"
                >
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M6 18L18 6M6 6l12 12"
                    />
                  </svg>
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Resource list */}
      {sortedResources.length === 0 ? (
        <p className="text-slate-400 text-sm italic py-4">
          No resources yet. Add links, references, or files above.
        </p>
      ) : (
        <div className="space-y-2">
          {sortedResources.map(resource => (
            <ResourceItem
              key={resource.id}
              resource={resource}
              projectId={projectId}
              onUpdate={updates => onUpdate(resource.id, updates)}
              onRemove={() => handleRemove(resource)}
            />
          ))}
        </div>
      )}
    </div>
  )
}
