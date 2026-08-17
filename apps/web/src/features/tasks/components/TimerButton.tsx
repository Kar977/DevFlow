import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Button } from "@/shared/ui";
import { isConflictError } from "@/shared/api/errorMessage";
import { useTimerStore } from "@/shared/store/timerStore";
import type { Task } from "@/features/tasks/hooks/useTasksQuery";
import { useTimerMutation } from "@/features/tasks/hooks/useTimerMutation";
import { formatElapsed } from "@/features/tasks/lib/trackedTime";

export function TimerButton({ task }: { task: Task }) {
  const { activeSession } = useTimerStore();
  const isActiveTask = activeSession?.taskId === task.id;
  const { start, stop, switchTo, isStarting, isStopping } = useTimerMutation(task);
  const [elapsedSeconds, setElapsedSeconds] = useState(0);

  useEffect(() => {
    if (!isActiveTask || !activeSession) return;
    const startMs = new Date(activeSession.startedAt).getTime();
    const id = setInterval(
      () => setElapsedSeconds(Math.floor((Date.now() - startMs) / 1000)),
      1000
    );
    return () => clearInterval(id);
  }, [isActiveTask, activeSession]);

  if (isActiveTask) {
    return (
      <Button variant="destructive" size="sm" onClick={() => stop()} disabled={isStopping}>
        Stop {formatElapsed(elapsedSeconds)}
      </Button>
    );
  }

  function handleStart() {
    start(undefined, {
      onError: (error) => {
        if (!isConflictError(error)) return;
        // The 409 tells us a session is active but not whose — read the
        // local store, which useTimerSync keeps in sync with the server's
        // active session (see that hook for why it's usually already correct
        // by the time this fires).
        const blocking = useTimerStore.getState().activeSession;
        if (!blocking) {
          toast.error("Masz już uruchomiony timer na innym zadaniu.");
          return;
        }
        toast.error(`Timer już działa: "${blocking.taskTitle}"`, {
          action: {
            label: "Zatrzymaj i przełącz",
            onClick: () => void switchTo(blocking.taskId),
          },
        });
      },
    });
  }

  return (
    <Button size="sm" variant="outline" onClick={handleStart} disabled={isStarting}>
      Start
    </Button>
  );
}
