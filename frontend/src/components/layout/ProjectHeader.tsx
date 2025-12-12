import type { WebinarType } from '../../types/project'
import { WEBINAR_TYPE_LABELS } from '../../types/project'
import { useProject } from '../../context/ProjectContext'

export interface ProjectHeaderProps {
  title: string
  webinarType: WebinarType
}

export function ProjectHeader({ title, webinarType }: ProjectHeaderProps) {
  const { goToList } = useProject()

  return (
    <div className="bg-slate-800/50 border-b border-slate-700">
      <div className="max-w-6xl mx-auto px-6 sm:px-10 lg:px-16 py-6">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div className="w-10 h-10 bg-gradient-to-br from-blue-500 to-cyan-400 rounded-xl flex items-center justify-center shadow-lg shadow-blue-500/20">
              <span className="text-white font-bold text-lg">W</span>
            </div>
            <div>
              <h1 className="text-xl font-semibold text-white">{title}</h1>
              <span className="text-sm text-slate-400">
                {WEBINAR_TYPE_LABELS[webinarType]}
              </span>
            </div>
          </div>
          <button
            onClick={goToList}
            className="flex items-center gap-2 px-4 py-2 text-slate-400 hover:text-white hover:bg-slate-700/50 rounded-lg transition-colors"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 19l-7-7m0 0l7-7m-7 7h18" />
            </svg>
            <span className="text-sm font-medium">Back to Projects</span>
          </button>
        </div>
      </div>
    </div>
  )
}
