import type { Task } from "@/features/tasks/hooks/useTasksQuery";

/** Statuses that mean a task can never be "overdue" — mirrors the backend's
 * `Task.OVERDUE_EXCLUDED_STATUSES` (apps/api core/models/task.py). Keep in sync. */
const OVERDUE_EXCLUDED_STATUSES = new Set(["done", "cancelled"]);

/**
 * Converts a `YYYY-MM-DD` date-input value to an ISO datetime at the end of
 * that day in the user's local timezone. "Due on the 20th" means the 20th
 * has fully passed, not midnight at its start.
 */
export function toDueDateIso(dateOnly: string): string {
  const [year, month, day] = dateOnly.split("-").map(Number);
  return new Date(year, month - 1, day, 23, 59, 59).toISOString();
}

/**
 * Converts an ISO datetime (as returned by the API) back to a `YYYY-MM-DD`
 * value for a date input, using the *local* calendar date. Never derive this
 * with `iso.slice(0, 10)` or `new Date(dateOnly)` — both interpret the string
 * as UTC midnight and can show the wrong day at negative UTC offsets.
 */
export function fromDueDateIso(iso: string): string {
  const date = new Date(iso);
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

/** Same overdue rule as the backend: past due_date and not done/cancelled. */
export function isOverdue(task: Pick<Task, "due_date" | "status">): boolean {
  if (!task.due_date) return false;
  if (OVERDUE_EXCLUDED_STATUSES.has(task.status)) return false;
  return new Date(task.due_date) < new Date();
}

/** Formats an ISO due date for display, e.g. "20 sierpnia 2026". */
export function formatDueDate(iso: string): string {
  return new Date(iso).toLocaleDateString("pl-PL", {
    day: "numeric",
    month: "long",
    year: "numeric",
  });
}
