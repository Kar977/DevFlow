/**
 * Polish labels for `Task.status` values.
 *
 * Shared between the task list filter (`TaskFilters`) and the project
 * cycle-time panel (`CycleTimePanel`) so the two can't drift into showing
 * different labels for the same status.
 */
export const TASK_STATUS_LABELS: Record<string, string> = {
  backlog: "Backlog",
  todo: "To Do",
  in_progress: "W toku",
  review: "Review",
  done: "Ukończone",
  cancelled: "Anulowane",
};

/** Falls back to the raw status string for anything not in the map above —
 * `Task.status` has no DB-level enum constraint, so an unrecognized value
 * shouldn't disappear from the UI, just render unlabeled. */
export function taskStatusLabel(status: string): string {
  return TASK_STATUS_LABELS[status] ?? status;
}
