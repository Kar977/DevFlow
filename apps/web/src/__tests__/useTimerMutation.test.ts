import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { renderHook, waitFor, act } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { http, HttpResponse } from "msw";
import { toast } from "sonner";
import React from "react";
import { server } from "./mocks/server";
import { useTimerMutation } from "@/features/tasks/hooks/useTimerMutation";
import { activeSessionKey } from "@/features/tasks/hooks/useActiveSessionQuery";
import { taskQueryKeys } from "@/features/tasks/hooks/useTasksQuery";
import { useTimerStore } from "@/shared/store/timerStore";
import { metricsQueryKeys } from "@/features/metrics/hooks/metricsQueryKeys";
import type { Task } from "@/features/tasks/hooks/useTasksQuery";

vi.mock("sonner", () => ({ toast: { error: vi.fn() } }));

const task: Task = {
  id: "task-b",
  title: "Task B",
  status: "todo",
  priority: "medium",
  project_id: "p1",
  created_by: "u1",
  created_at: "2024-01-01",
  updated_at: "2024-01-01",
};

function wrapper() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const invalidateSpy = vi.spyOn(qc, "invalidateQueries");
  const Wrapper = ({ children }: { children: React.ReactNode }) =>
    React.createElement(QueryClientProvider, { client: qc }, children);
  return { Wrapper, invalidateSpy };
}

beforeEach(() => {
  useTimerStore.getState().stopSession();
  useTimerStore.setState({ activeSession: null, elapsedSeconds: 0 });
  vi.mocked(toast.error).mockClear();
});

afterEach(() => {
  useTimerStore.getState().stopSession();
});

describe("useTimerMutation", () => {
  it("start: on success, syncs the store and invalidates both task and active-session queries", async () => {
    server.use(
      http.post("*/tasks/task-b/start", () =>
        HttpResponse.json({ id: "s1", started_at: "2024-01-01T10:00:00Z" }, { status: 201 })
      )
    );
    const { Wrapper, invalidateSpy } = wrapper();
    const { result } = renderHook(() => useTimerMutation(task), { wrapper: Wrapper });

    act(() => result.current.start());

    await waitFor(() => expect(useTimerStore.getState().activeSession?.taskId).toBe("task-b"));
    const invalidatedKeys = invalidateSpy.mock.calls.map((c) => c[0]?.queryKey);
    expect(invalidatedKeys).toContainEqual(taskQueryKeys.all);
    expect(invalidatedKeys).toContainEqual(activeSessionKey);
  });

  it("start: on 409, invalidates the active-session query but does not toast (caller handles it)", async () => {
    server.use(
      http.post("*/tasks/task-b/start", () =>
        HttpResponse.json(
          { error: { code: "session_active", message: "Active elsewhere.", details: {} } },
          { status: 409 }
        )
      )
    );
    const { Wrapper, invalidateSpy } = wrapper();
    const { result } = renderHook(() => useTimerMutation(task), { wrapper: Wrapper });

    act(() => result.current.start());

    await waitFor(() =>
      expect(invalidateSpy.mock.calls.map((c) => c[0]?.queryKey)).toContainEqual(activeSessionKey)
    );
    expect(toast.error).not.toHaveBeenCalled();
  });

  it("start: on a non-conflict error, shows the API's error message as a toast", async () => {
    server.use(
      http.post("*/tasks/task-b/start", () =>
        HttpResponse.json(
          { error: { code: "not_found", message: "Task not found.", details: {} } },
          { status: 404 }
        )
      )
    );
    const { Wrapper } = wrapper();
    const { result } = renderHook(() => useTimerMutation(task), { wrapper: Wrapper });

    act(() => result.current.start());

    await waitFor(() => expect(toast.error).toHaveBeenCalledWith("Task not found."));
  });

  it("stop: on success, clears the store and invalidates the metrics queries", async () => {
    useTimerStore.getState().startSession({
      taskId: "task-b",
      taskTitle: "Task B",
      startedAt: "2024-01-01T10:00:00Z",
    });
    server.use(
      http.post("*/tasks/task-b/stop", () =>
        HttpResponse.json({ id: "s1", ended_at: "2024-01-01T11:00:00Z", duration_seconds: 3600 })
      )
    );
    const { Wrapper, invalidateSpy } = wrapper();
    const { result } = renderHook(() => useTimerMutation(task), { wrapper: Wrapper });

    act(() => result.current.stop());

    await waitFor(() => expect(useTimerStore.getState().activeSession).toBeNull());
    const invalidatedKeys = invalidateSpy.mock.calls.map((c) => c[0]?.queryKey);
    expect(invalidatedKeys).toContainEqual(metricsQueryKeys.all);
  });

  it("switchTo: stops the currently active task, then starts this hook's task", async () => {
    const calls: string[] = [];
    server.use(
      http.post("*/tasks/task-a/stop", () => {
        calls.push("stop-a");
        return HttpResponse.json({ id: "s0", ended_at: "x", duration_seconds: 10 });
      }),
      http.post("*/tasks/task-b/start", () => {
        calls.push("start-b");
        return HttpResponse.json({ id: "s1", started_at: "2024-01-01T10:00:00Z" }, { status: 201 });
      })
    );
    const { Wrapper, invalidateSpy } = wrapper();
    const { result } = renderHook(() => useTimerMutation(task), { wrapper: Wrapper });

    await act(async () => {
      await result.current.switchTo("task-a");
    });

    expect(calls).toEqual(["stop-a", "start-b"]);
    await waitFor(() => expect(useTimerStore.getState().activeSession?.taskId).toBe("task-b"));
    const invalidatedKeys = invalidateSpy.mock.calls.map((c) => c[0]?.queryKey);
    expect(invalidatedKeys).toContainEqual(metricsQueryKeys.all);
  });

  it("switchTo: does not start the new task when stopping the old one fails", async () => {
    let startCalled = false;
    server.use(
      http.post("*/tasks/task-a/stop", () => HttpResponse.json({ error: { code: "no_active_session", message: "Gone.", details: {} } }, { status: 404 })),
      http.post("*/tasks/task-b/start", () => {
        startCalled = true;
        return HttpResponse.json({ id: "s1", started_at: "x" }, { status: 201 });
      })
    );
    const { Wrapper } = wrapper();
    const { result } = renderHook(() => useTimerMutation(task), { wrapper: Wrapper });

    await act(async () => {
      await result.current.switchTo("task-a");
    });

    expect(startCalled).toBe(false);
    expect(toast.error).toHaveBeenCalledWith("Gone.");
  });
});
