import { useState } from "react";
import { Link } from "react-router-dom";
import { AlertTriangle, X } from "lucide-react";
import { useOverdueTasksQuery } from "@/features/tasks/hooks/useOverdueTasksQuery";
import { formatDueDate } from "@/features/tasks/lib/dueDate";
import { pluralizeTasks } from "@/features/tasks/lib/plural";

const DISMISSED_KEY = "devflow-overdue-dismissed";
const MAX_TITLES = 3;

function readDismissedTotal(): number {
  const raw = sessionStorage.getItem(DISMISSED_KEY);
  const parsed = raw ? Number(raw) : 0;
  return Number.isFinite(parsed) ? parsed : 0;
}

/**
 * Dashboard-wide warning when the caller has overdue tasks in the active
 * organization. Mounted once in AppShell (see useTimerSync for the
 * precedent) so it's visible regardless of which page is open.
 *
 * Dismissal is session-only and keyed by the current overdue count: closing
 * it hides the banner until either a new browser session starts or the
 * count grows past what was dismissed (e.g. another task goes overdue).
 */
export function OverdueTasksBanner() {
  const { data } = useOverdueTasksQuery();
  const [dismissedTotal, setDismissedTotal] = useState(readDismissedTotal);

  if (!data || data.total === 0) return null;
  if (data.total <= dismissedTotal) return null;

  return (
    <div
      role="alert"
      className="mb-4 flex items-start gap-3 rounded-lg border border-red-200 bg-red-50 p-4 text-red-800"
    >
      <AlertTriangle className="h-5 w-5 shrink-0" />
      <div className="flex-1 space-y-1">
        <p className="text-sm font-medium">
          Masz {data.total} {pluralizeTasks(data.total)} po terminie.
        </p>
        <ul className="text-sm">
          {data.items.slice(0, MAX_TITLES).map((task) => (
            <li key={task.id}>
              {task.title}
              {task.due_date && (
                <span className="text-red-700/80"> — {formatDueDate(task.due_date)}</span>
              )}
            </li>
          ))}
        </ul>
        <Link to="/tasks" className="text-sm font-medium underline underline-offset-2">
          Zobacz zadania
        </Link>
      </div>
      <button
        type="button"
        aria-label="Zamknij"
        className="shrink-0 text-red-800/70 hover:text-red-800"
        onClick={() => {
          sessionStorage.setItem(DISMISSED_KEY, String(data.total));
          setDismissedTotal(data.total);
        }}
      >
        <X className="h-4 w-4" />
      </button>
    </div>
  );
}
