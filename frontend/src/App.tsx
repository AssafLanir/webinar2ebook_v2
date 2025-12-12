import { ProjectProvider, useProject } from './context/ProjectContext'
import { LandingPage } from './pages/LandingPage'
import { WorkspacePage } from './pages/WorkspacePage'

function AppContent() {
  const { hasProject } = useProject()

  if (!hasProject) {
    return <LandingPage />
  }

  return <WorkspacePage />
}

function App() {
  return (
    <ProjectProvider>
      <AppContent />
    </ProjectProvider>
  )
}

export default App
