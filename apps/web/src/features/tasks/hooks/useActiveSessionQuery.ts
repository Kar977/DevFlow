import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/shared/api/client";

export interface ActiveSession {
  id: string;
  task_id: string;
  task_title: string;
  started_at: string;
  elapsed_seconds: number;
  is_long_running: boolean;
  long_running_threshold_seconds: number;
}

export const activeSessionKey = ["tasks", "active-session"] as const;

/** The caller's currently running work session, if any — the server-side
 * source of truth that `useTimerSync` reconciles the local timer store
 * against (see that hook for why this matters). */
export function useActiveSessionQuery() {
  return useQuery({
    queryKey: activeSessionKey,
    queryFn: () =>
      apiClient
        .get("/tasks/sessions/active")
        .then((r) => (r.data as { data: ActiveSession | null }).data),
  });
}
