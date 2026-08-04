import { describe, it, expect, beforeEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { useTaskTrackedSeconds } from "@/features/tasks/hooks/useTaskTrackedSeconds";
import { useTimerStore } from "@/shared/store/timerStore";
import type { Task } from "@/features/tasks/hooks/useTasksQuery";

const baseTask: Task = {
  id: "task-1",
  title: "Fix bug",
  status: "in_progress",
  priority: "high",
  project_id: "p1",
  created_by: "u1",
  created_at: "2024-01-01",
  updated_at: "2024-01-01",
  tracked_seconds: 300,
};

beforeEach(() => {
  useTimerStore.setState({ activeSession: null, elapsedSeconds: 0 });
});

describe("useTaskTrackedSeconds", () => {
  it("returns just the persisted total when the task has no active session", () => {
    const { result } = renderHook(() => useTaskTrackedSeconds(baseTask));
    expect(result.current).toBe(300);
  });

  it("returns the persisted total when a DIFFERENT task is active", () => {
    useTimerStore.setState({
      activeSession: { taskId: "other-task", taskTitle: "Other", startedAt: new Date().toISOString() },
      elapsedSeconds: 0,
    });
    const { result } = renderHook(() => useTaskTrackedSeconds(baseTask));
    expect(result.current).toBe(300);
  });

  it("adds the live running interval when this task is active", async () => {
    const startedAt = new Date(Date.now() - 5000).toISOString();
    useTimerStore.setState({
      activeSession: { taskId: "task-1", taskTitle: "Fix bug", startedAt },
      elapsedSeconds: 0,
    });
    const { result } = renderHook(() => useTaskTrackedSeconds(baseTask));
    await waitFor(() => expect(result.current).toBeGreaterThanOrEqual(304));
  });
});
