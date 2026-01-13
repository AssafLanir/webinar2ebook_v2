import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { EditionMirror } from '../../src/components/tab3/EditionMirror'

describe('EditionMirror', () => {
  it('shows edition name', () => {
    render(
      <EditionMirror
        edition="qa"
        fidelity="faithful"
        onChangeClick={vi.fn()}
      />
    )
    expect(screen.getByText(/Q&A Edition/)).toBeInTheDocument()
  })

  it('shows fidelity for Q&A edition', () => {
    render(
      <EditionMirror
        edition="qa"
        fidelity="faithful"
        onChangeClick={vi.fn()}
      />
    )
    expect(screen.getByText(/Faithful/i)).toBeInTheDocument()
  })

  it('hides fidelity for Ideas edition', () => {
    render(
      <EditionMirror
        edition="ideas"
        fidelity="faithful"
        onChangeClick={vi.fn()}
      />
    )
    expect(screen.queryByText(/Faithful/i)).not.toBeInTheDocument()
  })

  it('calls onChangeClick when link clicked', () => {
    const onChangeClick = vi.fn()
    render(
      <EditionMirror
        edition="qa"
        fidelity="faithful"
        onChangeClick={onChangeClick}
      />
    )
    fireEvent.click(screen.getByText('Change in Tab 1'))
    expect(onChangeClick).toHaveBeenCalled()
  })
})
