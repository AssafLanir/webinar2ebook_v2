import { Button } from '../common/Button'
import type { TabIndex } from '../../types/project'

export interface TabNavigationProps {
  activeTab: TabIndex
  onPrevious: () => void
  onNext: () => void
  disabled?: boolean
}

export function TabNavigation({ activeTab, onPrevious, onNext, disabled }: TabNavigationProps) {
  const isFirstTab = activeTab === 1
  const isLastTab = activeTab === 4

  return (
    <div className="flex justify-between items-center pt-8 border-t border-slate-700 mt-10">
      <Button
        variant="secondary"
        onClick={onPrevious}
        disabled={isFirstTab || disabled}
      >
        ← Previous
      </Button>

      <span className="text-sm text-slate-400 font-medium">
        Step {activeTab} of 4
      </span>

      <Button
        variant="primary"
        onClick={onNext}
        disabled={isLastTab || disabled}
      >
        Next →
      </Button>
    </div>
  )
}
