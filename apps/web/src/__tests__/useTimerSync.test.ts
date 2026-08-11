import { describe, it, expect, beforeEach, afterEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { http, HttpResponse } from "msw";
import React from "react";
import { server } from "./mocks/server";
import { useTimerSync } from "@/features/tasks/hooks/useTimerSync";
import { useTimerStore } from "@/shared/store/timerStore";

function wrapper() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return ({ children }: { children: React.ReactNode }) =>
    React.createElement(QueryClientProvider, { client: qc }, children);
}

beforeEach(() => {
  useTimerStore.getState().stopSession();
  useTimerStore.setState({ activeSession: null, elapsedSeconds: 0 });
});

afterEach(() => {
  useTimerStore.getState().stopSession();
});

describe("useTimerSync", () => {
  it("does nothing when the server has no active session", async () => {
    let requested = false;
    server.use(
      http.get("*/tasks/sessions/active", () => {
        requested = true;
        return HttpResponse.json({ data: null });
      })
    );
    renderHook(() => useTimerSync(), { wrapper: wrapper() });
    await waitFor(() => expect(requested).toBe(true));
    expect(useTimerStore.getState().activeSession).toBeNull();
  });

  it("hydrates the store from a session the server reports as active", async () => {
    const startedAt = new Date(Date.now() - 5 * 60 * 1000).toISOString(); // 5 min ago
    server.use(
      http.get("*/tasks/sessions/active", () =>
        HttpResponse.json({
          data: { id: "s1", task_id: "task-1", task_title: "Wire rate limiter", started_at: startedAt },
        })
      )
    );

    renderHook(() => useTimerSync(), { wrapper: wrapper() });

    await waitFor(() => {
      expect(useTimerStore.getState().activeSession?.taskId).toBe("task-1");
    });
    expect(useTimerStore.getState().activeSession?.taskTitle).toBe("Wire rate limiter");
    // Must reflect the real elapsed time since startedAt, not reset to 0.
    expect(useTimerStore.getState().elapsedSeconds).toBeGreaterThanOrEqual(290);
  });

  it("clears a locally-stale session once the server reports none active", async () => {
    useTimerStore.getState().startSession({
      taskId: "stale-task",
      taskTitle: "Stale",
      startedAt: new Date().toISOString(),
    });
    server.use(
      http.get("*/tasks/sessions/active", () => HttpResponse.json({ data: null }))
    );

    renderHook(() => useTimerSync(), { wrapper: wrapper() });

    await waitFor(() => {
      expect(useTimerStore.getState().activeSession).toBeNull();
    });
  });
});
