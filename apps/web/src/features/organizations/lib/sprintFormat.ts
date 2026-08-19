import type { Sprint } from "@/features/organizations/hooks/useOrgSprints";

/** "2026-08-04" -> "04.08.2026" — these are plain calendar dates (no time
 * component), so formatting is a pure string operation; going through
 * `Date`/`toLocaleDateString` risks a timezone-driven off-by-one. */
export function formatSprintDate(dateOnly: string): string {
  const [year, month, day] = dateOnly.split("-");
  return `${day}.${month}.${year}`;
}

/** "Sprint 12 (05.08 – 18.08)" / "17.08 – 23.08" when the org has no
 * cadence (unnumbered sprints — see core.services.period.sprint_series). */
export function formatSprintLabel(sprint: Pick<Sprint, "number" | "start_date" | "end_date">): string {
  const range = `${formatSprintDate(sprint.start_date)} – ${formatSprintDate(sprint.end_date)}`;
  return sprint.number !== null ? `Sprint ${sprint.number} (${range})` : range;
}
