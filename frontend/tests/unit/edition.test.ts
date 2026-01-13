import { describe, it, expect } from 'vitest'
import type { Edition, Fidelity, Theme, Coverage, SegmentRef } from '../../src/types/edition'
import {
  EDITION_LABELS,
  EDITION_DESCRIPTIONS,
  FIDELITY_LABELS,
  COVERAGE_COLORS,
  DEFAULT_EDITION,
  DEFAULT_FIDELITY,
} from '../../src/types/edition'

describe('Edition Types', () => {
  it('should have valid edition values', () => {
    const qa: Edition = 'qa'
    const ideas: Edition = 'ideas'
    expect(qa).toBe('qa')
    expect(ideas).toBe('ideas')
  })

  it('should have valid fidelity values', () => {
    const faithful: Fidelity = 'faithful'
    const verbatim: Fidelity = 'verbatim'
    expect(faithful).toBe('faithful')
    expect(verbatim).toBe('verbatim')
  })

  it('should have valid coverage values', () => {
    const strong: Coverage = 'strong'
    const medium: Coverage = 'medium'
    const weak: Coverage = 'weak'
    expect(['strong', 'medium', 'weak']).toContain(strong)
    expect(['strong', 'medium', 'weak']).toContain(medium)
    expect(['strong', 'medium', 'weak']).toContain(weak)
  })
})

describe('SegmentRef', () => {
  it('should require canonical_hash for offset validity', () => {
    const segment: SegmentRef = {
      start_offset: 0,
      end_offset: 100,
      token_count: 25,
      text_preview: 'Hello world...',
      canonical_hash: 'abc123' + 'abc123'.repeat(9) + 'abcd', // 64 chars
    }
    expect(segment.canonical_hash).toBeDefined()
    expect(segment.canonical_hash.length).toBe(64)
  })
})

describe('Theme', () => {
  it('should have all required fields', () => {
    const theme: Theme = {
      id: 'theme-1',
      title: 'The Nature of Knowledge',
      one_liner: 'How knowledge grows through conjecture',
      keywords: ['epistemology', 'Popper'],
      coverage: 'strong',
      supporting_segments: [],
      include_in_generation: true,
    }
    expect(theme.id).toBe('theme-1')
    expect(theme.coverage).toBe('strong')
    expect(theme.include_in_generation).toBe(true)
  })
})

describe('Edition Labels and Descriptions', () => {
  it('should have labels for all editions', () => {
    expect(EDITION_LABELS.qa).toBe('Q&A Edition')
    expect(EDITION_LABELS.ideas).toBe('Ideas Edition')
  })

  it('should have descriptions for all editions', () => {
    expect(EDITION_DESCRIPTIONS.qa).toContain('interview')
    expect(EDITION_DESCRIPTIONS.ideas).toContain('Thematic')
  })

  it('should have fidelity labels', () => {
    expect(FIDELITY_LABELS.faithful).toContain('Faithful')
    expect(FIDELITY_LABELS.verbatim).toContain('Verbatim')
  })

  it('should have coverage colors', () => {
    expect(COVERAGE_COLORS.strong).toContain('green')
    expect(COVERAGE_COLORS.medium).toContain('yellow')
    expect(COVERAGE_COLORS.weak).toContain('red')
  })
})

describe('Default Values', () => {
  it('should have sensible defaults', () => {
    expect(DEFAULT_EDITION).toBe('qa')
    expect(DEFAULT_FIDELITY).toBe('faithful')
  })
})
