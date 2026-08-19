import { useMutation, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/shared/api/client";
import { metricsQueryKeys } from "@/features/metrics/hooks/metricsQueryKeys";
import { taskQueryKeys } from "./useTasksQuery";

// Create/update/delete can all move a metrics-visible number — created_at
// shifts completion-rate's denominator, an update may be the -> done
// transition, a delete removes a counted task — so all three invalidate
// unconditionally rather than trying to sniff which case applies.
function invalidateTaskAndMetricQueries(qc: ReturnType<typeof useQueryClient>): void {
  void qc.invalidateQueries({ queryKey: taskQueryKeys.all });
  void qc.invalidateQueries({ queryKey: metricsQueryKeys.all });
}

export function useCreateTask(projectId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: {
      title: string;
      description?: string;
      priority?: string;
      estimate_minutes?: number;
      assignee_id?: string;
      due_date?: string | null;
      sprint_start_date?: string | null;
    }) => apiClient.post("/tasks", { ...data, project_id: projectId }).then((r) => r.data),
    onSuccess: () => invalidateTaskAndMetricQueries(qc),
  });
}

export function useUpdateTask() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      taskId,
      data,
    }: {
      taskId: string;
      data: {
        title?: string;
        description?: string;
        status?: string;
        priority?: string;
        assignee_id?: string | null;
        due_date?: string | null;
        sprint_start_date?: string | null;
      };
    }) => apiClient.patch(`/tasks/${taskId}`, data).then((r) => r.data),
    onSuccess: () => invalidateTaskAndMetricQueries(qc),
  });
}

export function useDeleteTask() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (taskId: string) => apiClient.delete(`/tasks/${taskId}`),
    onSuccess: () => invalidateTaskAndMetricQueries(qc),
  });
}
