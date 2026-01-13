import type { Edition, Fidelity } from '../../types/edition'
import { EDITION_LABELS, FIDELITY_LABELS } from '../../types/edition'

interface EditionMirrorProps {
  edition: Edition
  fidelity: Fidelity
  onChangeClick: () => void
}

export function EditionMirror({ edition, fidelity, onChangeClick }: EditionMirrorProps) {
  return (
    <div className="flex items-center justify-between p-3 bg-gray-50 rounded-lg border">
      <div className="flex items-center gap-2">
        <span className="text-sm text-gray-600">Generating:</span>
        <span className="font-medium text-gray-900">{EDITION_LABELS[edition]}</span>
        {edition === 'qa' && (
          <>
            <span className="text-gray-400">·</span>
            <span className="text-sm text-gray-600">Fidelity: {FIDELITY_LABELS[fidelity]}</span>
          </>
        )}
      </div>
      <button
        onClick={onChangeClick}
        className="text-sm text-blue-600 hover:text-blue-800 hover:underline"
      >
        Change in Tab 1
      </button>
    </div>
  )
}
