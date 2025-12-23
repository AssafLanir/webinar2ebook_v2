/**
 * OpportunityList component for Tab 2 Visuals.
 *
 * Displays visual opportunities grouped by chapter with:
 * - Chapter headers
 * - OpportunityCard for each opportunity
 * - Empty state when no opportunities exist
 */

import type { VisualOpportunity, VisualAsset, VisualAssignment } from "../../types/visuals";
import { OpportunityCard } from "./OpportunityCard";

interface OpportunityListProps {
  projectId: string;
  opportunities: VisualOpportunity[];
  assignments: VisualAssignment[];
  assets: VisualAsset[];
  onAssign: (opportunityId: string) => void;
  onSkip: (opportunityId: string) => void;
  onUnassign: (opportunityId: string) => void;
}

interface ChapterGroup {
  chapterIndex: number;
  opportunities: VisualOpportunity[];
}

export function OpportunityList({
  projectId,
  opportunities,
  assignments,
  assets,
  onAssign,
  onSkip,
  onUnassign,
}: OpportunityListProps) {
  // Empty state
  if (opportunities.length === 0) {
    return (
      <div className="text-center py-12">
        <svg
          className="mx-auto h-12 w-12 text-gray-400"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M9 17V7m0 10a2 2 0 01-2 2H5a2 2 0 01-2-2V7a2 2 0 012-2h2a2 2 0 012 2m0 10a2 2 0 002 2h2a2 2 0 002-2M9 7a2 2 0 012-2h2a2 2 0 012 2m0 10V7m0 10a2 2 0 002 2h2a2 2 0 002-2V7a2 2 0 00-2-2h-2a2 2 0 00-2 2"
          />
        </svg>
        <h3 className="mt-2 text-sm font-medium text-gray-900">No visual opportunities</h3>
        <p className="mt-1 text-sm text-gray-500">
          Generate a draft in Tab 3 to create visual opportunities.
        </p>
      </div>
    );
  }

  // Group opportunities by chapter
  const groupedByChapter = opportunities.reduce<ChapterGroup[]>((groups, opp) => {
    const existingGroup = groups.find((g) => g.chapterIndex === opp.chapter_index);
    if (existingGroup) {
      existingGroup.opportunities.push(opp);
    } else {
      groups.push({ chapterIndex: opp.chapter_index, opportunities: [opp] });
    }
    return groups;
  }, []);

  // Sort groups by chapter index
  groupedByChapter.sort((a, b) => a.chapterIndex - b.chapterIndex);

  // Helper to find assignment for an opportunity
  const getAssignment = (opportunityId: string): VisualAssignment | undefined => {
    return assignments.find((a) => a.opportunity_id === opportunityId);
  };

  // Helper to find asset by ID
  const getAsset = (assetId: string | null | undefined): VisualAsset | undefined => {
    if (!assetId) return undefined;
    return assets.find((a) => a.id === assetId);
  };

  // Calculate stats
  const totalCount = opportunities.length;
  const assignedCount = assignments.filter((a) => a.status === "assigned").length;
  const skippedCount = assignments.filter((a) => a.status === "skipped").length;
  const unassignedCount = totalCount - assignedCount - skippedCount;

  return (
    <div className="space-y-6">
      {/* Summary stats */}
      <div className="flex items-center gap-4 text-sm text-gray-600">
        <span>
          <span className="font-medium text-gray-900">{totalCount}</span> opportunities
        </span>
        <span className="text-gray-300">|</span>
        <span>
          <span className="font-medium text-green-600">{assignedCount}</span> assigned
        </span>
        <span>
          <span className="font-medium text-gray-500">{skippedCount}</span> skipped
        </span>
        <span>
          <span className="font-medium text-amber-600">{unassignedCount}</span> remaining
        </span>
      </div>

      {/* Grouped opportunities */}
      {groupedByChapter.map((group) => (
        <div key={group.chapterIndex} className="space-y-3">
          <h3 className="text-sm font-semibold text-gray-700 border-b border-gray-200 pb-1">
            Chapter {group.chapterIndex}
          </h3>
          <div className="space-y-3">
            {group.opportunities.map((opp) => {
              const assignment = getAssignment(opp.id);
              const assignedAsset = assignment?.status === "assigned"
                ? getAsset(assignment.asset_id)
                : undefined;

              return (
                <OpportunityCard
                  key={opp.id}
                  projectId={projectId}
                  opportunity={opp}
                  assignment={assignment}
                  assignedAsset={assignedAsset}
                  onAssign={onAssign}
                  onSkip={onSkip}
                  onUnassign={onUnassign}
                />
              );
            })}
          </div>
        </div>
      ))}
    </div>
  );
}
