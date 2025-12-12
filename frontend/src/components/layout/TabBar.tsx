import type { TabIndex } from '../../types/project'
import { TAB_LABELS } from '../../types/project'

export interface TabBarProps {
  activeTab: TabIndex
  onTabChange: (tab: TabIndex) => void
  disabled?: boolean
}

const tabs: TabIndex[] = [1, 2, 3, 4]

export function TabBar({ activeTab, onTabChange, disabled }: TabBarProps) {
  return (
    <nav className="flex flex-wrap gap-2" aria-label="Tabs">
      {tabs.map(tab => {
        const isActive = activeTab === tab
        return (
          <button
            key={tab}
            onClick={() => onTabChange(tab)}
            disabled={disabled}
            className={`
              px-4 py-2 rounded-lg font-medium text-sm transition-all duration-200
              ${
                isActive
                  ? 'bg-gradient-to-r from-blue-500 to-cyan-500 text-white shadow-lg shadow-cyan-500/20'
                  : 'bg-slate-800 text-slate-300 hover:bg-slate-700 border border-slate-700'
              }
              ${disabled ? 'opacity-50 cursor-not-allowed' : ''}
            `}
            aria-current={isActive ? 'page' : undefined}
          >
            {TAB_LABELS[tab]}
          </button>
        )
      })}
    </nav>
  )
}
