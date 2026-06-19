import { describe, it, expect, beforeEach, vi, afterEach } from "vitest";
import { useTimerStore } from "@/shared/store/timerStore";

beforeEach(() => {
  vi.useFakeTimers();
  useTimerStore.setState({ activeSession: null, elapsedSeconds: 0, _intervalId: null });
});

afterEach(() => {
  useTimerStore.getState().stopSession();
  vi.useRealTimers();
});

describe("useTimerStore", () => {
  it("starts with no session", () => {
    expect(useTimerStore.getState().activeSession).toBeNull();
    expect(useTimerStore.getState().elapsedSeconds).toBe(0);
  });

  it("startSession sets activeSession and begins ticking", () => {
    useTimerStore.getState().startSession({ taskId: "t1", taskTitle: "Fix bug", startedAt: "2024-01-01T10:00:00Z" });
    expect(useTimerStore.getState().activeSession?.taskId).toBe("t1");

    vi.advanceTimersByTime(3000);
    expect(useTimerStore.getState().elapsedSeconds).toBe(3);
  });

  it("stopSession clears session and elapsed", () => {
    useTimerStore.getState().startSession({ taskId: "t1", taskTitle: "Fix bug", startedAt: "2024-01-01T10:00:00Z" });
    vi.advanceTimersByTime(2000);
    useTimerStore.getState().stopSession();

    expect(useTimerStore.getState().activeSession).toBeNull();
    expect(useTimerStore.getState().elapsedSeconds).toBe(0);
  });

  it("startSession on existing session resets elapsed", () => {
    useTimerStore.getState().startSession({ taskId: "t1", taskTitle: "Task 1", startedAt: "2024-01-01T10:00:00Z" });
    vi.advanceTimersByTime(5000);
    useTimerStore.getState().startSession({ taskId: "t2", taskTitle: "Task 2", startedAt: "2024-01-01T10:00:05Z" });

    expect(useTimerStore.getState().elapsedSeconds).toBe(0);
    expect(useTimerStore.getState().activeSession?.taskId).toBe("t2");
  });
});
