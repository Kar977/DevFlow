import { describe, it, expect, beforeEach } from "vitest";
import { renderHook } from "@testing-library/react";
import { useLongRunningTimer } from "@/features/tasks/hooks/useLongRunningTimer";
import { useTimerStore } from "@/shared/store/timerStore";

beforeEach(() => {
  useTimerStore.getState().stopSession();
  useTimerStore.setState({
    activeSession: null,
    elapsedSeconds: 0,
    longRunningThresholdSeconds: null,
  });
});

describe("useLongRunningTimer", () => {
  it("returns null when there is no active session", () => {
    const { result } = renderHook(() => useLongRunningTimer());
    expect(result.current).toBeNull();
  });

  it("returns null when elapsed time is below the server threshold", () => {
    useTimerStore.setState({
      activeSession: { taskId: "t1", taskTitle: "Task", startedAt: new Date().toISOString() },
      elapsedSeconds: 100,
      longRunningThresholdSeconds: 21600,
    });
    const { result } = renderHook(() => useLongRunningTimer());
    expect(result.current).toBeNull();
  });

  it("returns null when the threshold hasn't been hydrated yet", () => {
    useTimerStore.setState({
      activeSession: { taskId: "t1", taskTitle: "Task", startedAt: new Date().toISOString() },
      elapsedSeconds: 999_999,
      longRunningThresholdSeconds: null,
    });
    const { result } = renderHook(() => useLongRunningTimer());
    expect(result.current).toBeNull();
  });

  it("flags the session once elapsed time reaches the threshold", () => {
    useTimerStore.setState({
      activeSession: { taskId: "t1", taskTitle: "Fix rate limiter", startedAt: new Date().toISOString() },
      elapsedSeconds: 21600,
      longRunningThresholdSeconds: 21600,
    });
    const { result } = renderHook(() => useLongRunningTimer());
    expect(result.current).toEqual({
      taskId: "t1",
      taskTitle: "Fix rate limiter",
      elapsedSeconds: 21600,
    });
  });
});
