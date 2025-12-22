/**
 * Draft export utilities for copy/download functionality.
 */

/**
 * Slugify a title for use in filenames.
 *
 * Rules:
 * - lowercase
 * - spaces -> "-"
 * - remove chars not in [a-z0-9-_]
 * - collapse multiple dashes
 * - trim leading/trailing dashes
 */
export function slugifyTitle(title: string): string {
  return title
    .toLowerCase()
    .replace(/\s+/g, '-')           // spaces -> dashes
    .replace(/[^a-z0-9-_]/g, '')    // remove invalid chars
    .replace(/-+/g, '-')            // collapse multiple dashes
    .replace(/^-+|-+$/g, '')        // trim leading/trailing dashes
}

/**
 * Build a draft filename with format:
 * <project-title-slug>--draft--<YYYY-MM-DD>.<ext>
 *
 * Fallback if no title: project-<first8-of-project-id>
 */
export function buildDraftFilename(
  title: string | null | undefined,
  projectId: string | null | undefined,
  ext: 'md' | 'txt'
): string {
  const date = new Date().toISOString().split('T')[0] // YYYY-MM-DD

  let slug: string
  if (title && title.trim()) {
    slug = slugifyTitle(title.trim())
  } else if (projectId) {
    slug = `project-${projectId.slice(0, 8)}`
  } else {
    slug = 'draft'
  }

  // Ensure slug is not empty after processing
  if (!slug) {
    slug = 'draft'
  }

  return `${slug}--draft--${date}.${ext}`
}

/**
 * Download text content as a file.
 * Creates a temporary blob URL and triggers download via <a> element.
 */
export function downloadText(
  content: string,
  filename: string,
  mimeType: string
): void {
  const blob = new Blob([content], { type: mimeType })
  const url = URL.createObjectURL(blob)

  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)

  // Clean up the blob URL
  URL.revokeObjectURL(url)
}

/**
 * Download draft as Markdown file.
 */
export function downloadAsMarkdown(
  content: string,
  title: string | null | undefined,
  projectId: string | null | undefined
): void {
  const filename = buildDraftFilename(title, projectId, 'md')
  downloadText(content, filename, 'text/markdown; charset=utf-8')
}

/**
 * Download draft as plain text file.
 */
export function downloadAsText(
  content: string,
  title: string | null | undefined,
  projectId: string | null | undefined
): void {
  const filename = buildDraftFilename(title, projectId, 'txt')
  downloadText(content, filename, 'text/plain; charset=utf-8')
}
