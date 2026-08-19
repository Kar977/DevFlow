import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/shared/api/client";

export interface Task {
  id: string;
  title: string;
  description?: string | null;
  status: "backlog" | "todo" | "in_progress" | "review" | "done" | "cancelled";
  priority: "low" | "medium" | "high" | "critical";
  estimate_minutes?: number | null;
  assignee_id?: string | null;
  due_date?: string | null;
  project_id: string;
  created_by: string;
  created_at: string;
  updated_at: string;
  completed_at?: string | null;
  tracked_seconds?: number;
  /** null = backlog, a YYYY-MM-DD date = that sprint's start date. */
  sprint_start_date?: string | null;
}

interface TasksParams {
  project_id: string;
  status?: string;
  assignee_id?: string;
  /** Mutually exclusive with `backlog_only` — the backend prefers
   * `backlog_only` if both are somehow sent. */
  sprint_start_date?: string;
  backlog_only?: boolean;
  limit?: number;
  offset?: number;
}

export const taskQueryKeys = {
  all: ["tasks"] as const,
  list: (params: TasksParams) => [...taskQueryKeys.all, "list", params] as const,
  detail: (id: string) => [...taskQueryKeys.all, "detail", id] as const,
  // Nested under `all` so every existing task mutation (create/update/delete,
  // which all invalidate `taskQueryKeys.all`) refreshes the overdue banner
  // for free — no extra invalidation wiring needed.
  overdue: (orgId: string) => [...taskQueryKeys.all, "overdue", orgId] as const,
};

export function useTasksQuery(params: TasksParams) {
  return useQuery({
    queryKey: taskQueryKeys.list(params),
    queryFn: () =>
      apiClient
        .get("/tasks", { params })
        .then((r) => {
          const body = r.data as { data: Task[]; meta: { total: number } };
          return { items: body.data, total: body.meta.total };
        }),
    enabled: !!params.project_id,
  });
}
