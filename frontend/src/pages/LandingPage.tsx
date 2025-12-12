import { useState, useEffect } from 'react'
import { useProject } from '../context/ProjectContext'
import type { WebinarType, ProjectSummary } from '../types/project'
import { WEBINAR_TYPE_LABELS } from '../types/project'
import { fetchProjects, deleteProject as apiDeleteProject } from '../services/api'
import { Modal } from '../components/common'

const webinarTypeOptions = (Object.keys(WEBINAR_TYPE_LABELS) as WebinarType[]).map(key => ({
  value: key,
  label: WEBINAR_TYPE_LABELS[key],
}))

function formatDate(dateString: string): string {
  const date = new Date(dateString)
  return date.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export function LandingPage() {
  const { createProject, openProject, state } = useProject()

  // Project list state
  const [projects, setProjects] = useState<ProjectSummary[]>([])
  const [listLoading, setListLoading] = useState(true)
  const [listError, setListError] = useState<string | null>(null)

  // Create form state
  const [showCreateForm, setShowCreateForm] = useState(false)
  const [projectName, setProjectName] = useState('')
  const [webinarType, setWebinarType] = useState<WebinarType>('standard_presentation')
  const [touched, setTouched] = useState(false)

  // Delete confirmation state
  const [deleteTarget, setDeleteTarget] = useState<ProjectSummary | null>(null)
  const [isDeleting, setIsDeleting] = useState(false)
  const [deleteError, setDeleteError] = useState<string | null>(null)

  // Load projects on mount
  useEffect(() => {
    loadProjects()
  }, [])

  const loadProjects = async () => {
    setListLoading(true)
    setListError(null)
    try {
      const data = await fetchProjects()
      setProjects(data)
    } catch (error) {
      setListError(error instanceof Error ? error.message : 'Failed to load projects')
    } finally {
      setListLoading(false)
    }
  }

  const handleCreate = async () => {
    setTouched(true)
    if (projectName.trim()) {
      try {
        await createProject(projectName.trim(), webinarType)
        // Success - context will navigate to workspace
      } catch {
        // Error is handled in context
      }
    }
  }

  const handleOpen = async (projectId: string) => {
    try {
      await openProject(projectId)
    } catch {
      // Error is handled in context
    }
  }

  const handleDeleteClick = (project: ProjectSummary) => {
    setDeleteTarget(project)
    setDeleteError(null)
  }

  const handleDeleteConfirm = async () => {
    if (!deleteTarget) return

    setIsDeleting(true)
    setDeleteError(null)

    try {
      await apiDeleteProject(deleteTarget.id)
      // Remove from local list
      setProjects(prev => prev.filter(p => p.id !== deleteTarget.id))
      setDeleteTarget(null)
    } catch (error) {
      setDeleteError(error instanceof Error ? error.message : 'Failed to delete project')
    } finally {
      setIsDeleting(false)
    }
  }

  const handleDeleteCancel = () => {
    setDeleteTarget(null)
    setDeleteError(null)
  }

  const isValid = projectName.trim().length > 0
  const showError = touched && !isValid
  const isCreating = state.isLoading
  const apiError = state.error

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 relative overflow-hidden">
      {/* Background effects */}
      <div className="absolute inset-0 pointer-events-none">
        <div className="absolute top-20 left-1/4 w-72 h-72 bg-blue-500 rounded-full opacity-20 blur-[100px]" />
        <div className="absolute bottom-20 right-1/4 w-72 h-72 bg-cyan-500 rounded-full opacity-20 blur-[100px]" />
      </div>

      {/* Main content */}
      <div className="relative min-h-screen p-8">
        <div className="max-w-4xl mx-auto">
          {/* Header */}
          <div className="text-center mb-10">
            <div className="inline-flex items-center justify-center w-16 h-16 bg-gradient-to-br from-blue-500 to-cyan-400 rounded-2xl shadow-lg shadow-blue-500/25 mb-6">
              <span className="text-white font-bold text-3xl">W</span>
            </div>
            <h1 className="text-3xl font-bold text-white mb-2">Webinar2Ebook</h1>
            <p className="text-slate-400">
              Transform your webinar content into a polished ebook
            </p>
          </div>

          {/* Create New Project Button */}
          {!showCreateForm && (
            <div className="flex justify-center mb-8">
              <button
                onClick={() => setShowCreateForm(true)}
                className="px-6 py-3 bg-gradient-to-r from-blue-500 to-cyan-500 text-white font-semibold rounded-lg hover:from-blue-600 hover:to-cyan-600 shadow-lg shadow-cyan-500/25 transition-all"
              >
                + Create New Project
              </button>
            </div>
          )}

          {/* Create Form */}
          {showCreateForm && (
            <div className="bg-slate-800/80 backdrop-blur border border-slate-700 rounded-2xl p-8 shadow-xl mb-8 max-w-md mx-auto">
              <div className="flex justify-between items-center mb-6">
                <h2 className="text-xl font-semibold text-white">New Project</h2>
                <button
                  onClick={() => {
                    setShowCreateForm(false)
                    setProjectName('')
                    setTouched(false)
                  }}
                  className="text-slate-400 hover:text-white"
                >
                  ✕
                </button>
              </div>
              <div className="space-y-5">
                <div>
                  <label className="block text-sm font-medium text-slate-300 mb-2">
                    Project Name <span className="text-cyan-400">*</span>
                  </label>
                  <input
                    type="text"
                    value={projectName}
                    onChange={e => setProjectName(e.target.value)}
                    onBlur={() => setTouched(true)}
                    placeholder="Enter your project name"
                    className="w-full px-4 py-3 bg-slate-700/50 border border-slate-600 rounded-lg text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-cyan-500 focus:border-transparent transition-all"
                  />
                  {showError && (
                    <p className="mt-2 text-sm text-red-400">Project name is required</p>
                  )}
                </div>

                <div>
                  <label className="block text-sm font-medium text-slate-300 mb-2">
                    Webinar Type
                  </label>
                  <select
                    value={webinarType}
                    onChange={e => setWebinarType(e.target.value as WebinarType)}
                    className="w-full px-4 py-3 bg-slate-700/50 border border-slate-600 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-cyan-500 focus:border-transparent transition-all cursor-pointer"
                  >
                    {webinarTypeOptions.map(option => (
                      <option key={option.value} value={option.value} className="bg-slate-800">
                        {option.label}
                      </option>
                    ))}
                  </select>
                </div>

                {apiError && (
                  <div className="p-3 bg-red-500/10 border border-red-500/30 rounded-lg">
                    <p className="text-sm text-red-400">{apiError}</p>
                  </div>
                )}

                <button
                  onClick={handleCreate}
                  disabled={!isValid || isCreating}
                  className={`
                    w-full py-3 px-6 rounded-lg font-semibold transition-all duration-200
                    ${isValid && !isCreating
                      ? 'bg-gradient-to-r from-blue-500 to-cyan-500 text-white hover:from-blue-600 hover:to-cyan-600 shadow-lg shadow-cyan-500/25'
                      : 'bg-slate-700 text-slate-500 cursor-not-allowed'
                    }
                  `}
                >
                  {isCreating ? 'Creating...' : 'Create Project'}
                </button>
              </div>
            </div>
          )}

          {/* Project List */}
          <div className="bg-slate-800/80 backdrop-blur border border-slate-700 rounded-2xl p-6 shadow-xl">
            <h2 className="text-xl font-semibold text-white mb-6">Your Projects</h2>

            {listLoading && (
              <div className="text-center py-12">
                <div className="inline-block w-8 h-8 border-2 border-cyan-500 border-t-transparent rounded-full animate-spin" />
                <p className="text-slate-400 mt-4">Loading projects...</p>
              </div>
            )}

            {listError && (
              <div className="text-center py-12">
                <p className="text-red-400 mb-4">{listError}</p>
                <button
                  onClick={loadProjects}
                  className="px-4 py-2 bg-slate-700 text-white rounded-lg hover:bg-slate-600 transition-colors"
                >
                  Retry
                </button>
              </div>
            )}

            {!listLoading && !listError && projects.length === 0 && (
              <div className="text-center py-12">
                <div className="text-slate-500 mb-2">
                  <svg className="w-16 h-16 mx-auto mb-4 opacity-50" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
                  </svg>
                </div>
                <p className="text-slate-400 mb-4">No projects yet</p>
                <button
                  onClick={() => setShowCreateForm(true)}
                  className="text-cyan-400 hover:text-cyan-300 font-medium"
                >
                  Create your first project
                </button>
              </div>
            )}

            {!listLoading && !listError && projects.length > 0 && (
              <div className="space-y-3">
                {projects.map(project => (
                  <div
                    key={project.id}
                    className="flex items-center justify-between p-4 bg-slate-700/50 rounded-xl border border-slate-600 hover:border-slate-500 transition-colors"
                  >
                    <div className="flex-1 min-w-0">
                      <h3 className="text-white font-medium truncate">{project.name}</h3>
                      <div className="flex items-center gap-3 mt-1">
                        <span className="text-xs px-2 py-0.5 bg-slate-600 text-slate-300 rounded">
                          {WEBINAR_TYPE_LABELS[project.webinarType]}
                        </span>
                        <span className="text-xs text-slate-400">
                          Updated {formatDate(project.updatedAt)}
                        </span>
                      </div>
                    </div>
                    <div className="flex items-center gap-2 ml-4">
                      <button
                        onClick={() => handleOpen(project.id)}
                        disabled={isCreating}
                        className="px-4 py-2 bg-cyan-500/20 text-cyan-400 rounded-lg hover:bg-cyan-500/30 transition-colors font-medium disabled:opacity-50"
                      >
                        Open
                      </button>
                      <button
                        onClick={() => handleDeleteClick(project)}
                        disabled={isCreating}
                        className="px-3 py-2 text-slate-400 hover:text-red-400 hover:bg-red-500/10 rounded-lg transition-colors disabled:opacity-50"
                        title="Delete project"
                      >
                        <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                        </svg>
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Delete Confirmation Modal */}
      <Modal isOpen={deleteTarget !== null} onClose={handleDeleteCancel}>
        <div className="p-6">
          <div className="flex items-center gap-3 mb-4">
            <div className="w-10 h-10 bg-red-500/20 rounded-full flex items-center justify-center">
              <svg className="w-5 h-5 text-red-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
              </svg>
            </div>
            <h3 className="text-lg font-semibold text-white">Delete Project</h3>
          </div>

          <p className="text-slate-300 mb-2">
            Are you sure you want to delete{' '}
            <span className="font-semibold text-white">{deleteTarget?.name}</span>?
          </p>
          <p className="text-sm text-slate-400 mb-6">
            This action cannot be undone. All project data will be permanently removed.
          </p>

          {deleteError && (
            <div className="mb-4 p-3 bg-red-500/10 border border-red-500/30 rounded-lg">
              <p className="text-sm text-red-400">{deleteError}</p>
            </div>
          )}

          <div className="flex justify-end gap-3">
            <button
              onClick={handleDeleteCancel}
              disabled={isDeleting}
              className="px-4 py-2 text-slate-300 hover:text-white hover:bg-slate-700 rounded-lg transition-colors disabled:opacity-50"
            >
              Cancel
            </button>
            <button
              onClick={handleDeleteConfirm}
              disabled={isDeleting}
              className="px-4 py-2 bg-red-500 text-white rounded-lg hover:bg-red-600 transition-colors font-medium disabled:opacity-50"
            >
              {isDeleting ? 'Deleting...' : 'Delete'}
            </button>
          </div>
        </div>
      </Modal>
    </div>
  )
}
