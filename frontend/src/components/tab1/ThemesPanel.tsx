import { useState } from 'react'
import type { Theme } from '../../types/edition'
import { ThemeRow } from './ThemeRow'
import { Button } from '../common/Button'

interface ThemesPanelProps {
  themes: Theme[]
  onProposeThemes: () => void
  onAddTheme: (title: string, oneLiner: string) => void
  onAddSuggestions?: () => void
  onUpdateTheme: (id: string, updates: Partial<Theme>) => void
  onRemoveTheme: (id: string) => void
  onReorderThemes: (orderedIds: string[]) => void
  isProposing?: boolean
}

export function ThemesPanel({
  themes,
  onProposeThemes,
  onAddTheme,
  onAddSuggestions,
  onUpdateTheme,
  onRemoveTheme,
  onReorderThemes,
  isProposing = false,
}: ThemesPanelProps) {
  const hasThemes = themes.length > 0

  const handleMoveUp = (index: number) => {
    if (index <= 0) return
    const newOrder = [...themes]
    const temp = newOrder[index - 1]
    newOrder[index - 1] = newOrder[index]
    newOrder[index] = temp
    onReorderThemes(newOrder.map(t => t.id))
  }

  const handleMoveDown = (index: number) => {
    if (index >= themes.length - 1) return
    const newOrder = [...themes]
    const temp = newOrder[index + 1]
    newOrder[index + 1] = newOrder[index]
    newOrder[index] = temp
    onReorderThemes(newOrder.map(t => t.id))
  }

  const [showAddForm, setShowAddForm] = useState(false)
  const [newTitle, setNewTitle] = useState('')
  const [newOneLiner, setNewOneLiner] = useState('')

  const handleAddTheme = () => {
    const trimmedTitle = newTitle.trim()
    if (trimmedTitle) {
      onAddTheme(trimmedTitle, newOneLiner.trim())
      setNewTitle('')
      setNewOneLiner('')
      setShowAddForm(false)
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && newTitle.trim()) {
      handleAddTheme()
    } else if (e.key === 'Escape') {
      setShowAddForm(false)
      setNewTitle('')
      setNewOneLiner('')
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-medium text-gray-700">
          Themes (chapter structure)
        </h3>
        <div className="flex gap-2">
          <Button
            variant="secondary"
            size="sm"
            onClick={() => setShowAddForm(true)}
            disabled={isProposing || showAddForm}
          >
            + Add Theme
          </Button>
          {hasThemes && onAddSuggestions && (
            <Button
              variant="secondary"
              size="sm"
              onClick={onAddSuggestions}
              disabled={isProposing}
            >
              Add Suggestions
            </Button>
          )}
          <Button
            variant={hasThemes ? 'secondary' : 'primary'}
            size="sm"
            onClick={onProposeThemes}
            disabled={isProposing}
          >
            {isProposing ? 'Proposing...' : hasThemes ? 'Repropose' : 'Propose Themes'}
          </Button>
        </div>
      </div>

      {/* Add theme form */}
      {showAddForm && (
        <div className="p-3 bg-blue-50 border border-blue-200 rounded-lg space-y-2">
          <input
            type="text"
            value={newTitle}
            onChange={(e) => setNewTitle(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Theme title (e.g., 'The Power of Habits')"
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            autoFocus
          />
          <input
            type="text"
            value={newOneLiner}
            onChange={(e) => setNewOneLiner(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Brief description (optional)"
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          />
          <div className="flex justify-end gap-2">
            <Button
              variant="secondary"
              size="sm"
              onClick={() => {
                setShowAddForm(false)
                setNewTitle('')
                setNewOneLiner('')
              }}
            >
              Cancel
            </Button>
            <Button
              variant="primary"
              size="sm"
              onClick={handleAddTheme}
              disabled={!newTitle.trim()}
            >
              Add
            </Button>
          </div>
        </div>
      )}

      {!hasThemes && !isProposing && !showAddForm && (
        <div className="text-center py-8 text-gray-500 border-2 border-dashed rounded-lg">
          <p>No themes yet.</p>
          <p className="text-sm">Click "Propose Themes" to analyze your transcript, or "Add Theme" to create manually.</p>
        </div>
      )}

      {isProposing && (
        <div className="flex items-center justify-center py-8">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600" />
          <span className="ml-3 text-gray-600">Analyzing transcript...</span>
        </div>
      )}

      {hasThemes && (
        <div className="space-y-2">
          {themes.map((theme, index) => (
            <ThemeRow
              key={theme.id}
              theme={theme}
              onUpdate={(updates) => onUpdateTheme(theme.id, updates)}
              onRemove={() => onRemoveTheme(theme.id)}
              onMoveUp={() => handleMoveUp(index)}
              onMoveDown={() => handleMoveDown(index)}
              isFirst={index === 0}
              isLast={index === themes.length - 1}
            />
          ))}
        </div>
      )}
    </div>
  )
}
