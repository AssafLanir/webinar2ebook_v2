/**
 * OpportunityCard component for Tab 2 Visuals.
 *
 * Displays a visual opportunity with:
 * - Title, type, and rationale
 * - Assignment state (unassigned, assigned with thumbnail, or skipped)
 * - Actions: Assign, Skip, Unassign
 */

import type { VisualOpportunity, VisualAsset, VisualAssignment } from "../../types/visuals";
import { getAssetContentUrl } from "../../services/visualsApi";

interface OpportunityCardProps {
  projectId: string;
  opportunity: VisualOpportunity;
  assignment?: VisualAssignment;
  assignedAsset?: VisualAsset;
  onAssign: (opportunityId: string) => void;
  onSkip: (opportunityId: string) => void;
  onUnassign: (opportunityId: string) => void;
}

export function OpportunityCard({
  projectId,
  opportunity,
  assignment,
  assignedAsset,
  onAssign,
  onSkip,
  onUnassign,
}: OpportunityCardProps) {
  const isAssigned = assignment?.status === "assigned" && assignedAsset;
  const isSkipped = assignment?.status === "skipped";
  const isUnassigned = !assignment;

  // Visual type display
  const typeLabels: Record<string, string> = {
    diagram: "Diagram",
    chart: "Chart",
    table: "Table",
    screenshot: "Screenshot",
    illustration: "Illustration",
    photo: "Photo",
    infographic: "Infographic",
  };

  const typeLabel = typeLabels[opportunity.visual_type] || opportunity.visual_type;

  return (
    <div
      className={`border rounded-lg p-4 ${
        isSkipped
          ? "bg-gray-50 border-gray-200 opacity-60"
          : isAssigned
          ? "bg-green-50 border-green-200"
          : "bg-white border-gray-200"
      }`}
    >
      {/* Header */}
      <div className="flex items-start justify-between gap-2 mb-2">
        <div className="flex-1 min-w-0">
          <h4 className="font-medium text-gray-900 truncate" title={opportunity.title}>
            {opportunity.title}
          </h4>
          <div className="flex items-center gap-2 mt-1">
            <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-blue-100 text-blue-800">
              {typeLabel}
            </span>
            {opportunity.required && (
              <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-amber-100 text-amber-800">
                Required
              </span>
            )}
          </div>
        </div>

        {/* Status badge */}
        {isAssigned && (
          <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-green-100 text-green-800">
            Assigned
          </span>
        )}
        {isSkipped && (
          <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-gray-100 text-gray-600">
            Skipped
          </span>
        )}
      </div>

      {/* Rationale */}
      {opportunity.rationale && (
        <p className="text-sm text-gray-600 mb-3 line-clamp-2">{opportunity.rationale}</p>
      )}

      {/* Assigned asset preview */}
      {isAssigned && assignedAsset && (
        <div className="mb-3 flex items-center gap-3 p-2 bg-white rounded border border-green-200">
          <img
            src={getAssetContentUrl(projectId, assignedAsset.id, "thumb")}
            alt={assignedAsset.alt_text || assignedAsset.caption || assignedAsset.filename}
            className="w-12 h-12 object-cover rounded"
          />
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium text-gray-900 truncate">
              {assignedAsset.caption || assignedAsset.filename}
            </p>
            {assignedAsset.width && assignedAsset.height && (
              <p className="text-xs text-gray-500">
                {assignedAsset.width}×{assignedAsset.height}
              </p>
            )}
          </div>
        </div>
      )}

      {/* Actions */}
      <div className="flex items-center gap-2">
        {isUnassigned && (
          <>
            <button
              onClick={() => onAssign(opportunity.id)}
              className="flex-1 px-3 py-1.5 text-sm font-medium text-white bg-blue-600 rounded hover:bg-blue-700 transition-colors"
            >
              Assign Image
            </button>
            <button
              onClick={() => onSkip(opportunity.id)}
              className="px-3 py-1.5 text-sm font-medium text-gray-600 bg-gray-100 rounded hover:bg-gray-200 transition-colors"
            >
              Skip
            </button>
          </>
        )}

        {isAssigned && (
          <>
            <button
              onClick={() => onAssign(opportunity.id)}
              className="flex-1 px-3 py-1.5 text-sm font-medium text-blue-600 bg-blue-50 rounded hover:bg-blue-100 transition-colors"
            >
              Change Image
            </button>
            <button
              onClick={() => onUnassign(opportunity.id)}
              className="px-3 py-1.5 text-sm font-medium text-gray-600 bg-gray-100 rounded hover:bg-gray-200 transition-colors"
            >
              Remove
            </button>
          </>
        )}

        {isSkipped && (
          <button
            onClick={() => onAssign(opportunity.id)}
            className="flex-1 px-3 py-1.5 text-sm font-medium text-blue-600 bg-blue-50 rounded hover:bg-blue-100 transition-colors"
          >
            Assign Image Instead
          </button>
        )}
      </div>
    </div>
  );
}
