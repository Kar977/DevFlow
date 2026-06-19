import { useMutation, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/shared/api/client";
import { useTimerStore } from "@/shared/store/timerStore";
import { taskQueryKeys } from "./useTasksQuery";
import type { Task } from "./useTasksQuery";

export function useTimerMutation(task: Task) {
  const qc = useQueryClient();
  const { startSession, stopSession } = useTimerStore();

  const start = useMutation({
    mutationFn: () =>
      apiClient.post(`/tasks/${task.id}/start`).then((r) => r.data as { id: string; started_at: string }),
    onSuccess: (session) => {
      startSession({
        taskId: task.id,
        taskTitle: task.title,
        startedAt: session.started_at,
      });
      void qc.invalidateQueries({ queryKey: taskQueryKeys.all });
    },
  });

  const stop = useMutation({
    mutationFn: () => apiClient.post(`/tasks/${task.id}/stop`).then((r) => r.data),
    onSuccess: () => {
      stopSession();
      void qc.invalidateQueries({ queryKey: taskQueryKeys.all });
    },
  });

  return { start: start.mutate, stop: stop.mutate, isStarting: start.isPending, isStopping: stop.isPending };
}
