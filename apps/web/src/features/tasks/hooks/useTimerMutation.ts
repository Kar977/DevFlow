import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { apiClient } from "@/shared/api/client";
import { getErrorMessage, isConflictError } from "@/shared/api/errorMessage";
import { useTimerStore } from "@/shared/store/timerStore";
import { metricsQueryKeys } from "@/features/metrics/hooks/metricsQueryKeys";
import { activeSessionKey } from "./useActiveSessionQuery";
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
      void qc.invalidateQueries({ queryKey: activeSessionKey });
    },
    onError: (error) => {
      // A 409 means another task's timer is already running. That's not
      // shown here as a generic error — the caller (TimerButton) handles it
      // with a "stop and switch" action, since only it knows which button
      // the user actually clicked. Re-sync regardless, in case the local
      // store was stale about which session is active.
      void qc.invalidateQueries({ queryKey: activeSessionKey });
      if (!isConflictError(error)) {
        toast.error(getErrorMessage(error, "Nie udało się uruchomić timera."));
      }
    },
  });

  const stop = useMutation({
    mutationFn: () => apiClient.post(`/tasks/${task.id}/stop`).then((r) => r.data),
    onSuccess: () => {
      stopSession();
      void qc.invalidateQueries({ queryKey: taskQueryKeys.all });
      void qc.invalidateQueries({ queryKey: activeSessionKey });
      // Tracked minutes just landed — the productivity dashboard (if open)
      // would otherwise keep showing pre-stop numbers for up to its 30s
      // staleTime.
      void qc.invalidateQueries({ queryKey: metricsQueryKeys.all });
    },
    onError: (error) => {
      toast.error(getErrorMessage(error, "Nie udało się zatrzymać timera."));
      void qc.invalidateQueries({ queryKey: activeSessionKey });
    },
  });

  /** Stop the session currently running on `activeTaskId`, then start one on
   * this hook's task. Used by the "Zatrzymaj i przełącz" toast action — a
   * plain `apiClient` call rather than the `stop` mutation above, since that
   * one is bound to `task.id` and stopping requires the *other* task's id. */
  async function switchTo(activeTaskId: string): Promise<void> {
    try {
      await apiClient.post(`/tasks/${activeTaskId}/stop`);
    } catch (error) {
      toast.error(getErrorMessage(error, "Nie udało się zatrzymać poprzedniego timera."));
      void qc.invalidateQueries({ queryKey: activeSessionKey });
      return;
    }
    stopSession();
    void qc.invalidateQueries({ queryKey: taskQueryKeys.all });
    void qc.invalidateQueries({ queryKey: activeSessionKey });
    void qc.invalidateQueries({ queryKey: metricsQueryKeys.all });
    start.mutate();
  }

  return {
    start: start.mutate,
    stop: stop.mutate,
    switchTo,
    isStarting: start.isPending,
    isStopping: stop.isPending,
  };
}
