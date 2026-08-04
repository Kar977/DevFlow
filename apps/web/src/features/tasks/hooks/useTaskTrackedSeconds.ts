import { useEffect, useState } from "react";
import { useTimerStore } from "@/shared/store/timerStore";
import type { Task } from "./useTasksQuery";

/**
 * Total tracked time for a task: the persisted sum from past sessions
 * (`task.tracked_seconds`) plus, when this task's timer is currently
 * running, the live elapsed time of the in-progress interval.
 */
export function useTaskTrackedSeconds(task: Task): number {
  const { activeSession } = useTimerStore();
  const isActiveTask = activeSession?.taskId === task.id;
  const [liveSeconds, setLiveSeconds] = useState(0);

  useEffect(() => {
    if (!isActiveTask || !activeSession) {
      setLiveSeconds(0);
      return;
    }
    const startMs = new Date(activeSession.startedAt).getTime();
    const tick = () => setLiveSeconds(Math.floor((Date.now() - startMs) / 1000));
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, [isActiveTask, activeSession]);

  return (task.tracked_seconds ?? 0) + (isActiveTask ? liveSeconds : 0);
}
