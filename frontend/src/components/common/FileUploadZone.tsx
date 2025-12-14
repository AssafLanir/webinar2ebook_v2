import { useCallback, useState, useRef } from 'react'

const ALLOWED_EXTENSIONS = ['.pdf', '.ppt', '.pptx', '.doc', '.docx', '.jpg', '.jpeg', '.png']
const ALLOWED_MIME_TYPES = [
  'application/pdf',
  'application/vnd.ms-powerpoint',
  'application/vnd.openxmlformats-officedocument.presentationml.presentation',
  'application/msword',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  'image/jpeg',
  'image/png',
]
const MAX_FILE_SIZE = 10 * 1024 * 1024 // 10 MB

export interface FileUploadZoneProps {
  onFileSelect: (file: File) => void
  isUploading?: boolean
  uploadProgress?: number
  error?: string | null
  disabled?: boolean
}

export function FileUploadZone({
  onFileSelect,
  isUploading = false,
  uploadProgress,
  error,
  disabled = false,
}: FileUploadZoneProps) {
  const [isDragOver, setIsDragOver] = useState(false)
  const [validationError, setValidationError] = useState<string | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const validateFile = useCallback((file: File): string | null => {
    // Check file size
    if (file.size > MAX_FILE_SIZE) {
      return `File size exceeds maximum of 10MB (${(file.size / (1024 * 1024)).toFixed(1)}MB)`
    }

    // Check extension
    const extension = '.' + file.name.split('.').pop()?.toLowerCase()
    if (!ALLOWED_EXTENSIONS.includes(extension)) {
      return `File type "${extension}" is not supported. Allowed: ${ALLOWED_EXTENSIONS.join(', ')}`
    }

    // Check MIME type
    if (file.type && !ALLOWED_MIME_TYPES.includes(file.type)) {
      return `File type "${file.type}" is not supported`
    }

    return null
  }, [])

  const handleFile = useCallback(
    (file: File) => {
      setValidationError(null)
      const error = validateFile(file)
      if (error) {
        setValidationError(error)
        return
      }
      onFileSelect(file)
    },
    [validateFile, onFileSelect]
  )

  const handleDrop = useCallback(
    (e: React.DragEvent<HTMLDivElement>) => {
      e.preventDefault()
      setIsDragOver(false)
      if (disabled || isUploading) return

      const file = e.dataTransfer.files[0]
      if (file) {
        handleFile(file)
      }
    },
    [disabled, isUploading, handleFile]
  )

  const handleDragOver = useCallback(
    (e: React.DragEvent<HTMLDivElement>) => {
      e.preventDefault()
      if (!disabled && !isUploading) {
        setIsDragOver(true)
      }
    },
    [disabled, isUploading]
  )

  const handleDragLeave = useCallback((e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault()
    setIsDragOver(false)
  }, [])

  const handleClick = useCallback(() => {
    if (!disabled && !isUploading) {
      fileInputRef.current?.click()
    }
  }, [disabled, isUploading])

  const handleInputChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0]
      if (file) {
        handleFile(file)
      }
      // Reset input so same file can be selected again
      e.target.value = ''
    },
    [handleFile]
  )

  const displayError = error || validationError

  return (
    <div className="space-y-2">
      <div
        className={`
          relative border-2 border-dashed rounded-lg p-4 text-center cursor-pointer
          transition-all duration-200
          ${isDragOver ? 'border-cyan-400 bg-cyan-500/10' : 'border-slate-600 hover:border-slate-500'}
          ${disabled || isUploading ? 'opacity-50 cursor-not-allowed' : ''}
          ${displayError ? 'border-red-500/50' : ''}
        `}
        onDrop={handleDrop}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onClick={handleClick}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept={ALLOWED_EXTENSIONS.join(',')}
          onChange={handleInputChange}
          className="hidden"
          disabled={disabled || isUploading}
        />

        {isUploading ? (
          <div className="space-y-3 py-2">
            {/* Upload icon with animation */}
            <div className="relative w-12 h-12 mx-auto">
              <svg
                className="w-12 h-12 text-cyan-400"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={1.5}
                  d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"
                  className="animate-pulse"
                />
              </svg>
              {/* Spinning ring */}
              <svg
                className="absolute inset-0 w-12 h-12 animate-spin"
                fill="none"
                viewBox="0 0 24 24"
              >
                <circle
                  className="opacity-20"
                  cx="12"
                  cy="12"
                  r="10"
                  stroke="currentColor"
                  strokeWidth="2"
                />
                <path
                  className="text-cyan-400"
                  fill="currentColor"
                  d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
                />
              </svg>
            </div>

            {/* Progress bar */}
            <div className="w-full max-w-xs mx-auto">
              <div className="h-1.5 bg-slate-700 rounded-full overflow-hidden">
                <div
                  className="h-full bg-gradient-to-r from-cyan-500 to-blue-500 rounded-full transition-all duration-300 ease-out"
                  style={{
                    width: uploadProgress !== undefined ? `${uploadProgress}%` : '100%',
                    animation: uploadProgress === undefined ? 'indeterminate 1.5s ease-in-out infinite' : undefined,
                  }}
                />
              </div>
            </div>

            {/* Status text */}
            <p className="text-sm text-slate-300">
              {uploadProgress !== undefined ? (
                <>
                  Uploading... <span className="text-cyan-400 font-medium">{Math.round(uploadProgress)}%</span>
                </>
              ) : (
                <span className="text-slate-400">Uploading file...</span>
              )}
            </p>
          </div>
        ) : (
          <>
            <svg
              className={`w-8 h-8 mx-auto mb-2 ${isDragOver ? 'text-cyan-400' : 'text-slate-500'}`}
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={1.5}
                d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"
              />
            </svg>
            <p className="text-sm text-slate-400">
              <span className="text-cyan-400 font-medium">Click to upload</span> or drag and drop
            </p>
            <p className="text-xs text-slate-500 mt-1">
              PDF, PPT, PPTX, DOC, DOCX, JPG, PNG (max 10MB)
            </p>
          </>
        )}
      </div>

      {displayError && (
        <p className="text-sm text-red-400 flex items-center gap-1">
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
            />
          </svg>
          {displayError}
        </p>
      )}
    </div>
  )
}
