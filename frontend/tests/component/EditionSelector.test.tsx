import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { EditionSelector } from '../../src/components/tab1/EditionSelector'

describe('EditionSelector', () => {
  it('renders both edition options', () => {
    const onChange = vi.fn()
    render(<EditionSelector value="qa" onChange={onChange} />)

    expect(screen.getByText('Q&A Edition')).toBeInTheDocument()
    expect(screen.getByText('Ideas Edition')).toBeInTheDocument()
  })

  it('shows selected edition', () => {
    const onChange = vi.fn()
    render(<EditionSelector value="qa" onChange={onChange} />)

    const qaRadio = screen.getByRole('radio', { name: /Q&A Edition/i })
    expect(qaRadio).toBeChecked()
  })

  it('calls onChange when selection changes', () => {
    const onChange = vi.fn()
    render(<EditionSelector value="qa" onChange={onChange} />)

    const ideasRadio = screen.getByRole('radio', { name: /Ideas Edition/i })
    fireEvent.click(ideasRadio)

    expect(onChange).toHaveBeenCalledWith('ideas')
  })

  it('shows recommendation hint when provided', () => {
    const onChange = vi.fn()
    render(
      <EditionSelector
        value="qa"
        onChange={onChange}
        recommendedEdition="qa"
      />
    )

    expect(screen.getByText(/recommended/i)).toBeInTheDocument()
  })

  it('disables inputs when disabled prop is true', () => {
    const onChange = vi.fn()
    render(<EditionSelector value="qa" onChange={onChange} disabled />)

    const qaRadio = screen.getByRole('radio', { name: /Q&A Edition/i })
    const ideasRadio = screen.getByRole('radio', { name: /Ideas Edition/i })

    expect(qaRadio).toBeDisabled()
    expect(ideasRadio).toBeDisabled()
  })
})
