import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { ThemesPanel } from '../../src/components/tab1/ThemesPanel'
import type { Theme } from '../../src/types/edition'

const mockThemes: Theme[] = [
  {
    id: 't1',
    title: 'The Nature of Knowledge',
    one_liner: 'How knowledge grows',
    keywords: ['epistemology'],
    coverage: 'strong',
    supporting_segments: [],
    include_in_generation: true,
  },
  {
    id: 't2',
    title: 'Progress Through Criticism',
    one_liner: 'Error correction',
    keywords: ['criticism'],
    coverage: 'weak',
    supporting_segments: [],
    include_in_generation: true,
  },
]

describe('ThemesPanel', () => {
  it('renders theme list', () => {
    render(
      <ThemesPanel
        themes={mockThemes}
        onProposeThemes={vi.fn()}
        onUpdateTheme={vi.fn()}
        onRemoveTheme={vi.fn()}
        onReorderThemes={vi.fn()}
      />
    )

    expect(screen.getByText('The Nature of Knowledge')).toBeInTheDocument()
    expect(screen.getByText('Progress Through Criticism')).toBeInTheDocument()
  })

  it('shows coverage badges', () => {
    render(
      <ThemesPanel
        themes={mockThemes}
        onProposeThemes={vi.fn()}
        onUpdateTheme={vi.fn()}
        onRemoveTheme={vi.fn()}
        onReorderThemes={vi.fn()}
      />
    )

    expect(screen.getByText('Strong')).toBeInTheDocument()
    expect(screen.getByText('Weak')).toBeInTheDocument()
  })

  it('shows weak coverage warning', () => {
    render(
      <ThemesPanel
        themes={mockThemes}
        onProposeThemes={vi.fn()}
        onUpdateTheme={vi.fn()}
        onRemoveTheme={vi.fn()}
        onReorderThemes={vi.fn()}
      />
    )

    expect(screen.getByText(/limited source material/i)).toBeInTheDocument()
  })

  it('calls onProposeThemes when button clicked', () => {
    const onProposeThemes = vi.fn()
    render(
      <ThemesPanel
        themes={[]}
        onProposeThemes={onProposeThemes}
        onUpdateTheme={vi.fn()}
        onRemoveTheme={vi.fn()}
        onReorderThemes={vi.fn()}
      />
    )

    fireEvent.click(screen.getByText('Propose Themes'))
    expect(onProposeThemes).toHaveBeenCalled()
  })

  it('shows empty state when no themes', () => {
    render(
      <ThemesPanel
        themes={[]}
        onProposeThemes={vi.fn()}
        onUpdateTheme={vi.fn()}
        onRemoveTheme={vi.fn()}
        onReorderThemes={vi.fn()}
      />
    )

    expect(screen.getByText('No themes yet.')).toBeInTheDocument()
  })

  it('shows loading state when proposing', () => {
    render(
      <ThemesPanel
        themes={[]}
        onProposeThemes={vi.fn()}
        onUpdateTheme={vi.fn()}
        onRemoveTheme={vi.fn()}
        onReorderThemes={vi.fn()}
        isProposing
      />
    )

    expect(screen.getByText('Analyzing transcript...')).toBeInTheDocument()
  })
})
