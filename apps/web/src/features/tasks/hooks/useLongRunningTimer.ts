import { useTimerStore } from "@/shared/store/timerStore";

export interface LongRunningTimer {
  taskId: string;
  taskTitle: string;
  elapsedSeconds: number;
}

/**
 * The active session, but only once it has run past the server-configured
 * "forgotten timer" threshold — otherwise null.
 *
 * The server is the source of truth for the threshold itself
 * (`longRunningThresholdSeconds`, hydrated by useTimerSync from
 * GET /tasks/sessions/active), but *crossing* it is evaluated here, locally,
 * against the store's `elapsedSeconds` — which already ticks once a second.
 * That split means no polling is needed: `useActiveSessionQuery` has no
 * `refetchInterval`, yet this hook still notices the crossing within a
 * second of it happening, because it re-renders every time the store ticks.
 */
export function useLongRunningTimer(): LongRunningTimer | null {
  const activeSession = useTimerStore((s) => s.activeSession);
  const elapsedSeconds = useTimerStore((s) => s.elapsedSeconds);
  const thresholdSeconds = useTimerStore((s) => s.longRunningThresholdSeconds);

  if (!activeSession || thresholdSeconds === null) return null;
  if (elapsedSeconds < thresholdSeconds) return null;

  return {
    taskId: activeSession.taskId,
    taskTitle: activeSession.taskTitle,
    elapsedSeconds,
  };
}
