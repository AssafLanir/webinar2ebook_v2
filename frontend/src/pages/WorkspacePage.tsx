import { useProject } from '../context/ProjectContext'
import { TabBar, TabNavigation, ProjectHeader } from '../components/layout'
import { Tab1Content } from '../components/tab1/Tab1Content'
import { Tab2Content } from '../components/tab2/Tab2Content'
import { Tab3Content } from '../components/tab3/Tab3Content'
import { Tab4Content } from '../components/tab4/Tab4Content'
import { Toast } from '../components/common/Toast'
import type { TabIndex } from '../types/project'

export function WorkspacePage() {
  const { state, setActiveTab, saveProject, clearSaveError } = useProject()
  const { project, activeTab, isSaving, saveError } = state

  if (!project) {
    return null
  }

  const handleTabChange = async (newTab: TabIndex) => {
    if (newTab === activeTab) return

    // Save before switching tabs
    const saved = await saveProject()
    if (saved) {
      setActiveTab(newTab)
    }
    // If save failed, error will be shown via Toast and user stays on current tab
  }

  const handlePrevious = async () => {
    if (activeTab > 1) {
      await handleTabChange((activeTab - 1) as TabIndex)
    }
  }

  const handleNext = async () => {
    if (activeTab < 4) {
      await handleTabChange((activeTab + 1) as TabIndex)
    }
  }

  const renderTabContent = () => {
    switch (activeTab) {
      case 1:
        return <Tab1Content />
      case 2:
        return <Tab2Content />
      case 3:
        return <Tab3Content />
      case 4:
        return <Tab4Content />
      default:
        return null
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900">
      {/* Header */}
      <ProjectHeader title={project.name} webinarType={project.webinarType} />

      {/* Main content - centered with generous padding */}
      <div className="max-w-6xl mx-auto px-6 sm:px-10 lg:px-16 py-8">
        <TabBar activeTab={activeTab} onTabChange={handleTabChange} disabled={isSaving} />

        <div className="mt-6">{renderTabContent()}</div>

        <TabNavigation
          activeTab={activeTab}
          onPrevious={handlePrevious}
          onNext={handleNext}
          disabled={isSaving}
        />
      </div>

      {/* Save error toast */}
      {saveError && (
        <Toast
          message={saveError}
          type="error"
          onClose={clearSaveError}
          action={{
            label: 'Retry',
            onClick: () => {
              clearSaveError()
              saveProject()
            },
          }}
        />
      )}

      {/* Saving indicator */}
      {isSaving && (
        <div className="fixed bottom-4 left-4 bg-slate-700 text-slate-200 px-4 py-2 rounded-lg shadow-lg flex items-center gap-2">
          <div className="w-4 h-4 border-2 border-cyan-500 border-t-transparent rounded-full animate-spin" />
          <span className="text-sm">Saving...</span>
        </div>
      )}
    </div>
  )
}
