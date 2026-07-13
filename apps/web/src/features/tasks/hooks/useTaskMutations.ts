import { useMutation, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/shared/api/client";
import { taskQueryKeys } from "./useTasksQuery";

export function useCreateTask(projectId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: {
      title: string;
      description?: string;
      priority?: string;
      estimate_minutes?: number;
      assignee_id?: string;
    }) => apiClient.post("/tasks", { ...data, project_id: projectId }).then((r) => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: taskQueryKeys.all }),
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
      };
    }) => apiClient.patch(`/tasks/${taskId}`, data).then((r) => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: taskQueryKeys.all }),
  });
}

export function useDeleteTask() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (taskId: string) => apiClient.delete(`/tasks/${taskId}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: taskQueryKeys.all }),
  });
}
