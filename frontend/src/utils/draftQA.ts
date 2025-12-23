/**
 * Draft QA utilities for quality checks.
 *
 * All checks are regex-based and run client-side for fast performance.
 */

export type QAIssueType =
  | 'repeated-word'
  | 'double-space'
  | 'multiple-punctuation'
  | 'heading-level-jump'
  | 'long-paragraph'

export interface QAIssue {
  type: QAIssueType
  message: string
  /** Character offset in the text where issue starts */
  position: number
  /** Length of the problematic text */
  length: number
  /** The actual problematic text */
  text: string
  /** Human-readable location (e.g., "Paragraph 3") */
  location: string
}

export interface QAResult {
  issues: QAIssue[]
  totalIssues: number
  checkedAt: Date
}

// Configuration
const LONG_PARAGRAPH_THRESHOLD = 1500 // characters

/**
 * Run all QA checks on the draft text.
 */
export function runQAChecks(text: string): QAResult {
  const issues: QAIssue[] = [
    ...checkRepeatedWords(text),
    ...checkDoubleSpaces(text),
    ...checkMultiplePunctuation(text),
    ...checkHeadingLevelJumps(text),
    ...checkLongParagraphs(text),
  ]

  // Sort by position
  issues.sort((a, b) => a.position - b.position)

  return {
    issues,
    totalIssues: issues.length,
    checkedAt: new Date(),
  }
}

/**
 * Check for repeated words (e.g., "the the", "and and").
 */
function checkRepeatedWords(text: string): QAIssue[] {
  const issues: QAIssue[] = []
  // Match word repeated with whitespace between (case-insensitive)
  const regex = /\b(\w+)\s+\1\b/gi
  let match

  while ((match = regex.exec(text)) !== null) {
    const word = match[1].toLowerCase()
    // Skip intentional repetitions like "very very" emphasis or common patterns
    if (['ha', 'he', 'ho', 'la', 'na', 'no', 'so', 'bye'].includes(word)) {
      continue
    }

    issues.push({
      type: 'repeated-word',
      message: `Repeated word: "${match[1]}"`,
      position: match.index,
      length: match[0].length,
      text: match[0],
      location: getLocationDescription(text, match.index),
    })
  }

  return issues
}

/**
 * Check for double or multiple consecutive spaces.
 */
function checkDoubleSpaces(text: string): QAIssue[] {
  const issues: QAIssue[] = []
  const regex = / {2,}/g
  let match

  while ((match = regex.exec(text)) !== null) {
    // Skip if it's at the start of a line (could be intentional indentation in code blocks)
    const beforeText = text.slice(Math.max(0, match.index - 1), match.index)
    if (beforeText === '\n' || match.index === 0) {
      continue
    }

    issues.push({
      type: 'double-space',
      message: `${match[0].length} consecutive spaces`,
      position: match.index,
      length: match[0].length,
      text: match[0],
      location: getLocationDescription(text, match.index),
    })
  }

  return issues
}

/**
 * Check for multiple consecutive punctuation marks (except valid ellipsis).
 */
function checkMultiplePunctuation(text: string): QAIssue[] {
  const issues: QAIssue[] = []
  // Match 2+ of the same punctuation, or mixed punctuation like "!?"
  const regex = /([!?]){2,}|([.]{4,})/g
  let match

  while ((match = regex.exec(text)) !== null) {
    // Skip valid ellipsis (exactly 3 dots or unicode ellipsis)
    if (match[0] === '...' || match[0] === '…') {
      continue
    }

    issues.push({
      type: 'multiple-punctuation',
      message: `Multiple punctuation: "${match[0]}"`,
      position: match.index,
      length: match[0].length,
      text: match[0],
      location: getLocationDescription(text, match.index),
    })
  }

  return issues
}

/**
 * Check for heading level jumps (e.g., H2 directly to H4, skipping H3).
 */
function checkHeadingLevelJumps(text: string): QAIssue[] {
  const issues: QAIssue[] = []
  // Match markdown headings: # H1, ## H2, etc.
  const headingRegex = /^(#{1,6})\s+(.+)$/gm
  const headings: Array<{ level: number; position: number; text: string; title: string }> = []

  let match
  while ((match = headingRegex.exec(text)) !== null) {
    headings.push({
      level: match[1].length,
      position: match.index,
      text: match[0],
      title: match[2].trim(),
    })
  }

  // Check for level jumps
  for (let i = 1; i < headings.length; i++) {
    const prev = headings[i - 1]
    const curr = headings[i]

    // Going deeper: should only increase by 1
    if (curr.level > prev.level && curr.level - prev.level > 1) {
      issues.push({
        type: 'heading-level-jump',
        message: `Heading jumps from H${prev.level} to H${curr.level} (skipped H${prev.level + 1})`,
        position: curr.position,
        length: curr.text.length,
        text: curr.text,
        location: `Heading "${curr.title.slice(0, 30)}${curr.title.length > 30 ? '...' : ''}"`,
      })
    }
  }

  return issues
}

/**
 * Check for very long paragraphs.
 */
function checkLongParagraphs(text: string): QAIssue[] {
  const issues: QAIssue[] = []
  // Split by double newlines (paragraph breaks)
  const paragraphs = text.split(/\n\n+/)
  let currentPosition = 0

  for (let i = 0; i < paragraphs.length; i++) {
    const para = paragraphs[i]

    // Skip headings, code blocks, and short content
    const trimmed = para.trim()
    if (
      trimmed.startsWith('#') ||
      trimmed.startsWith('```') ||
      trimmed.startsWith('    ') ||
      trimmed.length <= LONG_PARAGRAPH_THRESHOLD
    ) {
      currentPosition += para.length + 2 // +2 for \n\n
      continue
    }

    // Count actual content (excluding markdown formatting)
    const contentLength = trimmed
      .replace(/\*\*[^*]+\*\*/g, '') // Remove bold
      .replace(/\*[^*]+\*/g, '')     // Remove italic
      .replace(/\[[^\]]+\]\([^)]+\)/g, '') // Remove links
      .length

    if (contentLength > LONG_PARAGRAPH_THRESHOLD) {
      issues.push({
        type: 'long-paragraph',
        message: `Paragraph is ${contentLength.toLocaleString()} characters (consider splitting)`,
        position: currentPosition,
        length: Math.min(100, para.length), // Only highlight first 100 chars
        text: trimmed.slice(0, 50) + '...',
        location: `Paragraph ${i + 1}`,
      })
    }

    currentPosition += para.length + 2
  }

  return issues
}

/**
 * Get a human-readable location description for a position in text.
 */
function getLocationDescription(text: string, position: number): string {
  // Count paragraphs up to this position
  const textBefore = text.slice(0, position)
  const paragraphCount = (textBefore.match(/\n\n/g) || []).length + 1

  // Find if we're near a heading
  const lines = textBefore.split('\n')
  for (let i = lines.length - 1; i >= 0 && i >= lines.length - 5; i--) {
    const line = lines[i].trim()
    if (line.startsWith('#')) {
      const title = line.replace(/^#+\s*/, '').slice(0, 25)
      return `Near "${title}${line.length > 30 ? '...' : ''}"`
    }
  }

  return `Paragraph ${paragraphCount}`
}

/**
 * Get issue type label for display.
 */
export function getIssueTypeLabel(type: QAIssueType): string {
  const labels: Record<QAIssueType, string> = {
    'repeated-word': 'Repeated Word',
    'double-space': 'Extra Spaces',
    'multiple-punctuation': 'Punctuation',
    'heading-level-jump': 'Heading Structure',
    'long-paragraph': 'Long Paragraph',
  }
  return labels[type]
}

/**
 * Get issue type color for display.
 */
export function getIssueTypeColor(type: QAIssueType): string {
  const colors: Record<QAIssueType, string> = {
    'repeated-word': 'text-yellow-400',
    'double-space': 'text-blue-400',
    'multiple-punctuation': 'text-orange-400',
    'heading-level-jump': 'text-red-400',
    'long-paragraph': 'text-purple-400',
  }
  return colors[type]
}
