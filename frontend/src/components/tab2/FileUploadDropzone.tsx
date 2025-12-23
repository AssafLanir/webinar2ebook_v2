/**
 * Drag-and-drop file upload zone for visual assets.
 *
 * Features:
 * - Drag-and-drop or click to select
 * - Visual feedback during drag
 * - File type validation (PNG, JPEG, WebP)
 * - Multiple file selection
 */

import { useState, useCallback, useRef } from "react";

interface FileUploadDropzoneProps {
  onFilesSelected: (files: File[]) => void;
  disabled?: boolean;
  maxFiles?: number;
}

const ACCEPTED_TYPES = ["image/png", "image/jpeg", "image/webp"];
const ACCEPTED_EXTENSIONS = [".png", ".jpg", ".jpeg", ".webp"];

export function FileUploadDropzone({
  onFilesSelected,
  disabled = false,
  maxFiles = 10,
}: FileUploadDropzoneProps) {
  const [isDragOver, setIsDragOver] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const validateFiles = useCallback(
    (files: FileList | File[]): File[] => {
      const validFiles: File[] = [];
      const errors: string[] = [];

      const fileArray = Array.from(files);

      if (fileArray.length > maxFiles) {
        setError(`Maximum ${maxFiles} files per upload`);
        return [];
      }

      for (const file of fileArray) {
        if (!ACCEPTED_TYPES.includes(file.type)) {
          errors.push(`${file.name}: unsupported type`);
          continue;
        }
        validFiles.push(file);
      }

      if (errors.length > 0) {
        setError(errors.join(", "));
      } else {
        setError(null);
      }

      return validFiles;
    },
    [maxFiles]
  );

  const handleDragOver = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      e.stopPropagation();
      if (!disabled) {
        setIsDragOver(true);
      }
    },
    [disabled]
  );

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(false);
  }, []);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      e.stopPropagation();
      setIsDragOver(false);

      if (disabled) return;

      const files = e.dataTransfer.files;
      const validFiles = validateFiles(files);
      if (validFiles.length > 0) {
        onFilesSelected(validFiles);
      }
    },
    [disabled, validateFiles, onFilesSelected]
  );

  const handleClick = useCallback(() => {
    if (!disabled && fileInputRef.current) {
      fileInputRef.current.click();
    }
  }, [disabled]);

  const handleFileInput = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const files = e.target.files;
      if (files) {
        const validFiles = validateFiles(files);
        if (validFiles.length > 0) {
          onFilesSelected(validFiles);
        }
      }
      // Reset input so same file can be selected again
      e.target.value = "";
    },
    [validateFiles, onFilesSelected]
  );

  return (
    <div className="space-y-2">
      <div
        onClick={handleClick}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        className={`
          border-2 border-dashed rounded-lg p-8 text-center cursor-pointer
          transition-colors duration-200
          ${
            disabled
              ? "border-gray-200 bg-gray-50 cursor-not-allowed"
              : isDragOver
                ? "border-blue-500 bg-blue-50"
                : "border-gray-300 hover:border-gray-400 hover:bg-gray-50"
          }
        `}
      >
        <input
          ref={fileInputRef}
          type="file"
          multiple
          accept={ACCEPTED_EXTENSIONS.join(",")}
          onChange={handleFileInput}
          className="hidden"
          disabled={disabled}
        />

        <div className="flex flex-col items-center gap-2">
          <svg
            className={`w-10 h-10 ${isDragOver ? "text-blue-500" : "text-gray-400"}`}
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"
            />
          </svg>

          <div className="text-sm text-gray-600">
            {disabled ? (
              <span>Upload disabled</span>
            ) : isDragOver ? (
              <span className="text-blue-600 font-medium">Drop files here</span>
            ) : (
              <>
                <span className="text-blue-600 font-medium">Click to upload</span>
                <span> or drag and drop</span>
              </>
            )}
          </div>

          <p className="text-xs text-gray-500">PNG, JPG, WebP up to 10MB each</p>
        </div>
      </div>

      {error && (
        <p className="text-sm text-red-600 flex items-center gap-1">
          <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
            <path
              fillRule="evenodd"
              d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z"
              clipRule="evenodd"
            />
          </svg>
          {error}
        </p>
      )}
    </div>
  );
}
