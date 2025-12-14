import type { ReactElement } from 'react'
import type { Resource } from '../../types/project'
import { Button } from '../common/Button'
import { getFileDownloadUrl } from '../../services/api'
import { formatFileSize } from '../../utils/formatFileSize'

export interface FileResourceItemProps {
  resource: Resource
  projectId: string
  onRemove: () => void
  onUpdateLabel: (label: string) => void
}

/**
 * Get file type icon based on MIME type.
 */
function getFileIcon(mimeType?: string): ReactElement {
  if (!mimeType) {
    return (
      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth={1.5}
          d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z"
        />
      </svg>
    )
  }

  if (mimeType === 'application/pdf') {
    return (
      <svg className="w-5 h-5 text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth={1.5}
          d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z"
        />
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 13h6m-6 4h6" />
      </svg>
    )
  }

  if (mimeType.startsWith('image/')) {
    return (
      <svg className="w-5 h-5 text-green-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth={1.5}
          d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z"
        />
      </svg>
    )
  }

  if (mimeType.includes('powerpoint') || mimeType.includes('presentation')) {
    return (
      <svg
        className="w-5 h-5 text-orange-400"
        fill="none"
        stroke="currentColor"
        viewBox="0 0 24 24"
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth={1.5}
          d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z"
        />
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 9h6v6H9z" />
      </svg>
    )
  }

  if (mimeType.includes('word') || mimeType.includes('document')) {
    return (
      <svg className="w-5 h-5 text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth={1.5}
          d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z"
        />
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth={1.5}
          d="M9 9h6M9 13h6M9 17h4"
        />
      </svg>
    )
  }

  // Default file icon
  return (
    <svg className="w-5 h-5 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={1.5}
        d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z"
      />
    </svg>
  )
}

export function FileResourceItem({
  resource,
  projectId,
  onRemove,
  onUpdateLabel,
}: FileResourceItemProps) {
  const downloadUrl = resource.fileId ? getFileDownloadUrl(projectId, resource.fileId) : null

  return (
    <div className="flex items-start gap-3 p-3 bg-slate-700/50 border border-slate-600 rounded-lg">
      {/* File icon */}
      <div className="flex-shrink-0 mt-1">{getFileIcon(resource.mimeType)}</div>

      {/* File info */}
      <div className="flex-1 min-w-0 space-y-1">
        <input
          type="text"
          value={resource.label}
          onChange={e => onUpdateLabel(e.target.value)}
          className="w-full bg-transparent border-none outline-none focus:ring-0 text-white font-medium placeholder-slate-400 truncate"
          placeholder="Resource title..."
        />
        <div className="flex items-center gap-2 text-xs text-slate-400">
          <span className="truncate">{resource.fileName}</span>
          {resource.fileSize && (
            <>
              <span className="text-slate-600">•</span>
              <span>{formatFileSize(resource.fileSize)}</span>
            </>
          )}
        </div>
      </div>

      {/* Actions */}
      <div className="flex items-center gap-1">
        {downloadUrl && (
          <a
            href={downloadUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center justify-center rounded-lg p-1.5 text-slate-300 hover:bg-slate-600 transition-colors"
            title="Download file"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"
              />
            </svg>
          </a>
        )}
        <Button variant="ghost" size="sm" onClick={onRemove}>
          <svg className="w-4 h-4 text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M6 18L18 6M6 6l12 12"
            />
          </svg>
        </Button>
      </div>
    </div>
  )
}
