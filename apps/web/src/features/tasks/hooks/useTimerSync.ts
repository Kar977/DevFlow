import { useEffect } from "react";
import { useTimerStore } from "@/shared/store/timerStore";
import { useActiveSessionQuery } from "./useActiveSessionQuery";

/**
 * Reconciles the local timer store with the server's active session.
 *
 * The timer store lives only in memory — it isn't persisted and has no way
 * to learn about a session on its own. That used to mean a page reload
 * silently forgot a running timer, and a session left open by a closed tab
 * became invisible and unstoppable from the UI (every later Start attempt
 * just failed with a 409 nothing displayed). Mount this once, high in the
 * tree, to make the server authoritative: on load, and whenever the
 * active-session query is invalidated (see `useTimerMutation`), it pulls
 * the local store back in sync.
 */
export function useTimerSync(): void {
  const { data: activeSession, isSuccess } = useActiveSessionQuery();
  const localTaskId = useTimerStore((s) => s.activeSession?.taskId);
  const startSession = useTimerStore((s) => s.startSession);
  const stopSession = useTimerStore((s) => s.stopSession);

  useEffect(() => {
    if (!isSuccess) return;

    if (activeSession === null) {
      if (localTaskId !== undefined) stopSession();
      return;
    }

    if (localTaskId === activeSession.task_id) return;

    startSession({
      taskId: activeSession.task_id,
      taskTitle: activeSession.task_title,
      startedAt: activeSession.started_at,
    });
    // startSession() always resets elapsedSeconds to 0, but a hydrated
    // session usually started in the past — without this, the sidebar's
    // TimerIndicator would show 00:00 for a session running for hours.
    const elapsedSinceStart = Math.floor(
      (Date.now() - new Date(activeSession.started_at).getTime()) / 1000
    );
    useTimerStore.setState({ elapsedSeconds: Math.max(elapsedSinceStart, 0) });
  }, [activeSession, isSuccess, localTaskId, startSession, stopSession]);
}
