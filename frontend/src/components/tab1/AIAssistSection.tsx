/**
 * AIAssistSection - AI-assisted actions for Tab 1
 *
 * Provides buttons for:
 * - Clean Transcript (AI)
 * - Suggest Outline (AI)
 * - Suggest Resources (AI)
 */

import { useProject } from '../../context/ProjectContext'
import { Button } from '../common/Button'
import { cleanTranscript, suggestOutline, suggestResources, ApiException } from '../../services/api'

export function AIAssistSection() {
  const { state, dispatch } = useProject()
  const { project, aiAction } = state

  const isLoading = aiAction.inProgress !== null
  const hasTranscript = (project?.transcriptText?.length ?? 0) > 0

  const handleCleanTranscript = async () => {
    if (!project?.transcriptText || isLoading) return

    dispatch({ type: 'START_AI_ACTION', payload: 'clean-transcript' })

    try {
      const response = await cleanTranscript(project.transcriptText)
      dispatch({
        type: 'AI_ACTION_SUCCESS',
        payload: {
          type: 'clean-transcript',
          cleanedTranscript: response.cleaned_transcript,
        },
      })
    } catch (error) {
      const message = error instanceof ApiException
        ? error.message
        : error instanceof Error
          ? error.message
          : 'Failed to clean transcript'
      dispatch({ type: 'AI_ACTION_ERROR', payload: message })
    }
  }

  const handleSuggestOutline = async () => {
    if (!project?.transcriptText || isLoading) return

    dispatch({ type: 'START_AI_ACTION', payload: 'suggest-outline' })

    try {
      const response = await suggestOutline(project.transcriptText)
      dispatch({
        type: 'AI_ACTION_SUCCESS',
        payload: {
          type: 'suggest-outline',
          items: response.items,
          selected: new Set(response.items.map((_, i) => i)), // Select all by default
        },
      })
    } catch (error) {
      const message = error instanceof ApiException
        ? error.message
        : error instanceof Error
          ? error.message
          : 'Failed to suggest outline'
      dispatch({ type: 'AI_ACTION_ERROR', payload: message })
    }
  }

  const handleSuggestResources = async () => {
    if (!project?.transcriptText || isLoading) return

    dispatch({ type: 'START_AI_ACTION', payload: 'suggest-resources' })

    try {
      const response = await suggestResources(project.transcriptText)
      dispatch({
        type: 'AI_ACTION_SUCCESS',
        payload: {
          type: 'suggest-resources',
          resources: response.resources,
          selected: new Set(response.resources.map((_, i) => i)), // Select all by default
        },
      })
    } catch (error) {
      const message = error instanceof ApiException
        ? error.message
        : error instanceof Error
          ? error.message
          : 'Failed to suggest resources'
      dispatch({ type: 'AI_ACTION_ERROR', payload: message })
    }
  }

  return (
    <div className="flex flex-wrap items-center gap-3">
      <span className="text-sm text-slate-400 font-medium">AI Assist:</span>

      <Button
        variant="secondary"
        size="sm"
        onClick={handleCleanTranscript}
        disabled={!hasTranscript || isLoading}
        title={!hasTranscript ? 'Add transcript text first' : undefined}
      >
        {aiAction.inProgress === 'clean-transcript' ? (
          <>
            <LoadingSpinner />
            <span className="ml-2">Cleaning...</span>
          </>
        ) : (
          'Clean Transcript (AI)'
        )}
      </Button>

      <Button
        variant="secondary"
        size="sm"
        onClick={handleSuggestOutline}
        disabled={!hasTranscript || isLoading}
        title={!hasTranscript ? 'Add transcript text first' : undefined}
      >
        {aiAction.inProgress === 'suggest-outline' ? (
          <>
            <LoadingSpinner />
            <span className="ml-2">Analyzing...</span>
          </>
        ) : (
          'Suggest Outline (AI)'
        )}
      </Button>

      <Button
        variant="secondary"
        size="sm"
        onClick={handleSuggestResources}
        disabled={!hasTranscript || isLoading}
        title={!hasTranscript ? 'Add transcript text first' : undefined}
      >
        {aiAction.inProgress === 'suggest-resources' ? (
          <>
            <LoadingSpinner />
            <span className="ml-2">Finding...</span>
          </>
        ) : (
          'Suggest Resources (AI)'
        )}
      </Button>

      {/* Error display */}
      {aiAction.error && (
        <div className="flex items-center gap-2 text-sm text-red-400">
          <span>{aiAction.error}</span>
          <button
            onClick={handleCleanTranscript}
            className="text-cyan-400 hover:text-cyan-300 underline"
          >
            Retry
          </button>
        </div>
      )}
    </div>
  )
}

function LoadingSpinner() {
  return (
    <svg
      className="animate-spin h-4 w-4 text-current"
      xmlns="http://www.w3.org/2000/svg"
      fill="none"
      viewBox="0 0 24 24"
    >
      <circle
        className="opacity-25"
        cx="12"
        cy="12"
        r="10"
        stroke="currentColor"
        strokeWidth="4"
      />
      <path
        className="opacity-75"
        fill="currentColor"
        d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
      />
    </svg>
  )
}
