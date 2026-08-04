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
  tracked_seconds?: number;
}

interface TasksParams {
  project_id: string;
  status?: string;
  assignee_id?: string;
  limit?: number;
  offset?: number;
}

export const taskQueryKeys = {
  all: ["tasks"] as const,
  list: (params: TasksParams) => [...taskQueryKeys.all, "list", params] as const,
  detail: (id: string) => [...taskQueryKeys.all, "detail", id] as const,
};

export function useTasksQuery(params: TasksParams) {
  return useQuery({
    queryKey: taskQueryKeys.list(params),
    queryFn: () =>
      apiClient
        .get("/tasks", { params })
        .then((r) => r.data as { items: Task[]; total: number }),
    enabled: !!params.project_id,
  });
}
