/**
 * Legacy project.visuals → visualPlan.assets migration helper.
 *
 * Spec 005 introduces VisualPlan.assets as the canonical location for visual assets.
 * Legacy projects may have assets in project.visuals (deprecated).
 * This helper merges legacy visuals into visualPlan.assets in-memory (no DB mutation).
 */

import type { VisualAsset, VisualPlan } from "../types/visuals";

/**
 * Migrate legacy project.visuals to visualPlan.assets.
 *
 * Rules:
 * - If visualPlan.assets already has items, they take precedence (no duplicates by id)
 * - Legacy visuals are appended if their id doesn't exist in visualPlan.assets
 * - Returns a new VisualPlan object (does not mutate input)
 *
 * @param legacyVisuals - The deprecated project.visuals array
 * @param visualPlan - The current visualPlan (may be undefined/null)
 * @returns Migrated VisualPlan with merged assets
 */
export function migrateVisualAssets(
  legacyVisuals: VisualAsset[] | undefined | null,
  visualPlan: VisualPlan | undefined | null
): VisualPlan {
  // Start with canonical empty structure
  const result: VisualPlan = {
    opportunities: visualPlan?.opportunities ?? [],
    assets: [...(visualPlan?.assets ?? [])],
    assignments: visualPlan?.assignments ?? [],
  };

  // If no legacy visuals, return as-is
  if (!legacyVisuals || legacyVisuals.length === 0) {
    return result;
  }

  // Build set of existing asset IDs for deduplication
  const existingIds = new Set(result.assets?.map((a) => a.id) ?? []);

  // Append legacy visuals that aren't already in assets
  for (const legacy of legacyVisuals) {
    if (!existingIds.has(legacy.id)) {
      result.assets?.push(legacy);
      existingIds.add(legacy.id);
    }
  }

  return result;
}

/**
 * Ensure a VisualPlan has all required fields with defaults.
 *
 * Use this when loading a project to guarantee the structure is complete.
 *
 * @param visualPlan - The raw visualPlan from API response
 * @returns VisualPlan with all fields initialized
 */
export function normalizeVisualPlan(
  visualPlan: Partial<VisualPlan> | undefined | null
): VisualPlan {
  return {
    opportunities: visualPlan?.opportunities ?? [],
    assets: visualPlan?.assets ?? [],
    assignments: visualPlan?.assignments ?? [],
  };
}
