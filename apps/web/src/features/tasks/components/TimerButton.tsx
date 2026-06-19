import { useEffect, useState } from "react";
import { Button } from "@/shared/ui";
import { useTimerStore } from "@/shared/store/timerStore";
import type { Task } from "@/features/tasks/hooks/useTasksQuery";
import { useTimerMutation } from "@/features/tasks/hooks/useTimerMutation";

function formatElapsed(ms: number) {
  const s = Math.floor(ms / 1000);
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
}

export function TimerButton({ task }: { task: Task }) {
  const { activeSession } = useTimerStore();
  const isActiveTask = activeSession?.taskId === task.id;
  const { start, stop, isStarting, isStopping } = useTimerMutation(task);
  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    if (!isActiveTask || !activeSession) return;
    const startMs = new Date(activeSession.startedAt).getTime();
    const id = setInterval(() => setElapsed(Date.now() - startMs), 1000);
    return () => clearInterval(id);
  }, [isActiveTask, activeSession]);

  if (isActiveTask) {
    return (
      <Button variant="destructive" size="sm" onClick={() => stop()} disabled={isStopping}>
        Stop {formatElapsed(elapsed)}
      </Button>
    );
  }

  return (
    <Button size="sm" variant="outline" onClick={() => start()} disabled={isStarting || !!activeSession}>
      Start
    </Button>
  );
}
