import type { Theme } from '../../types/edition'
import { ThemeRow } from './ThemeRow'
import { Button } from '../common/Button'

interface ThemesPanelProps {
  themes: Theme[]
  onProposeThemes: () => void
  onAddSuggestions?: () => void
  onUpdateTheme: (id: string, updates: Partial<Theme>) => void
  onRemoveTheme: (id: string) => void
  onReorderThemes: (orderedIds: string[]) => void
  isProposing?: boolean
}

export function ThemesPanel({
  themes,
  onProposeThemes,
  onAddSuggestions,
  onUpdateTheme,
  onRemoveTheme,
  onReorderThemes: _onReorderThemes,
  isProposing = false,
}: ThemesPanelProps) {
  // onReorderThemes is passed but not yet used - will be implemented for drag-and-drop
  void _onReorderThemes
  const hasThemes = themes.length > 0

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-medium text-gray-700">
          Themes (chapter structure)
        </h3>
        <div className="flex gap-2">
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

      {!hasThemes && !isProposing && (
        <div className="text-center py-8 text-gray-500 border-2 border-dashed rounded-lg">
          <p>No themes yet.</p>
          <p className="text-sm">Click "Propose Themes" to analyze your transcript.</p>
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
          {themes.map((theme) => (
            <ThemeRow
              key={theme.id}
              theme={theme}
              onUpdate={(updates) => onUpdateTheme(theme.id, updates)}
              onRemove={() => onRemoveTheme(theme.id)}
            />
          ))}
        </div>
      )}
    </div>
  )
}
