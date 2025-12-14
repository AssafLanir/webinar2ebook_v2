/**
 * Format file size in human-readable format.
 *
 * @param bytes - File size in bytes
 * @param decimals - Number of decimal places (default: 1)
 * @returns Formatted string like "1.5 MB" or "256 KB"
 *
 * @example
 * formatFileSize(1024) // "1 KB"
 * formatFileSize(1536, 2) // "1.50 KB"
 * formatFileSize(1048576) // "1 MB"
 * formatFileSize(0) // "0 B"
 */
export function formatFileSize(bytes: number, decimals: number = 1): string {
  if (bytes === 0) return '0 B'

  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))

  // Ensure we don't go beyond our sizes array
  const index = Math.min(i, sizes.length - 1)

  const value = bytes / Math.pow(k, index)

  // For whole numbers, don't show decimals
  if (value === Math.floor(value)) {
    return `${value} ${sizes[index]}`
  }

  return `${value.toFixed(decimals)} ${sizes[index]}`
}
