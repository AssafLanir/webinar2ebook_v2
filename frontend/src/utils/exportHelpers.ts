import type { Project } from '../types/project'
import { WEBINAR_TYPE_LABELS } from '../types/project'

/**
 * Generates a Markdown ebook from the project data
 * Following the structure defined in contracts/README.md
 */
export function generateMarkdown(project: Project): string {
  const lines: string[] = []

  // Title
  const title = project.finalTitle || project.name
  lines.push(`# ${title}`)
  lines.push('')

  // Subtitle
  if (project.finalSubtitle) {
    lines.push(`## ${project.finalSubtitle}`)
    lines.push('')
  }

  lines.push('---')
  lines.push('')

  // Credits
  if (project.creditsText) {
    lines.push(`**Credits**: ${project.creditsText}`)
    lines.push('')
  }

  // Source info
  lines.push(`**Generated from**: ${project.name} (${WEBINAR_TYPE_LABELS[project.webinarType]})`)
  lines.push('')
  lines.push('---')
  lines.push('')

  // Table of Contents
  lines.push('## Table of Contents')
  lines.push('')

  const sortedOutline = [...project.outlineItems].sort((a, b) => a.order - b.order)
  let chapterNum = 0

  sortedOutline.forEach(item => {
    if (item.level === 1) {
      chapterNum++
      lines.push(`- Chapter ${chapterNum}: ${item.title}`)
    } else {
      const indent = '  '.repeat(item.level - 1)
      lines.push(`${indent}- ${item.title}`)
    }
  })

  if (sortedOutline.length === 0) {
    lines.push('*No chapters defined*')
  }

  lines.push('')
  lines.push('---')
  lines.push('')

  // Included Visuals
  lines.push('## Included Visuals')
  lines.push('')

  const selectedVisuals = project.visuals.filter(v => v.selected)
  selectedVisuals.forEach(visual => {
    lines.push(`- [${visual.title}] ${visual.description}`)
  })

  if (selectedVisuals.length === 0) {
    lines.push('*No visuals selected*')
  }

  lines.push('')
  lines.push('---')
  lines.push('')

  // Content
  lines.push('## Content')
  lines.push('')
  lines.push(project.draftText || '*No content written yet*')
  lines.push('')
  lines.push('---')
  lines.push('')

  // Export timestamp
  const exportDate = new Date().toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
  lines.push(`*Exported on ${exportDate}*`)

  return lines.join('\n')
}

/**
 * Generates a safe filename from the title
 */
export function generateFilename(project: Project): string {
  const title = project.finalTitle || project.name
  // Remove special characters and replace spaces with hyphens
  const safeName = title
    .toLowerCase()
    .replace(/[^a-z0-9\s-]/g, '')
    .replace(/\s+/g, '-')
    .replace(/-+/g, '-')
    .slice(0, 50) // Limit length

  return `${safeName || 'ebook'}-ebook.md`
}

/**
 * Triggers a file download in the browser
 */
export function downloadMarkdown(project: Project): void {
  const content = generateMarkdown(project)
  const filename = generateFilename(project)

  // Create blob
  const blob = new Blob([content], { type: 'text/markdown;charset=utf-8' })

  // Create download link
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename

  // Trigger download
  document.body.appendChild(link)
  link.click()

  // Cleanup
  document.body.removeChild(link)
  URL.revokeObjectURL(url)
}
