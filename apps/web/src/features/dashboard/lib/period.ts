import type { Sprint } from "@/features/organizations/hooks/useOrgSprints";

export type PeriodMode = "current" | "previous" | "custom";

export interface DashboardWindow {
  date_from: string;
  date_to: string;
}

/**
 * Picks the current/previous sprint's dates out of a series fetched from
 * `GET /organizations/{id}/sprints` — never re-derive sprint boundaries on
 * the frontend, always read them off the backend's series.
 *
 * Expects `sprints` fetched with `back: 1, forward: 0` (oldest first), so
 * the current sprint is the last element and the previous one — if any —
 * is right before it.
 */
export function windowFromSprints(
  sprints: Sprint[] | undefined,
  mode: "current" | "previous"
): DashboardWindow | undefined {
  if (!sprints || sprints.length === 0) return undefined;
  const currentIndex = sprints.findIndex((s) => s.is_current);
  if (currentIndex === -1) return undefined;
  const target =
    mode === "current" ? sprints[currentIndex] : sprints[currentIndex - 1];
  if (!target) return undefined;
  return { date_from: target.start_date, date_to: target.end_date };
}
