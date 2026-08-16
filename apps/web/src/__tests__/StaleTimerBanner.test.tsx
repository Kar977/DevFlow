import { describe, it, expect, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { http, HttpResponse } from "msw";
import { server } from "./mocks/server";
import { StaleTimerBanner } from "@/features/tasks/components/StaleTimerBanner";
import { useTimerStore } from "@/shared/store/timerStore";

function renderBanner() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const tree = (
    <QueryClientProvider client={qc}>
      <StaleTimerBanner />
    </QueryClientProvider>
  );
  const utils = render(tree);
  return { ...utils, rerenderBanner: () => utils.rerender(tree) };
}

function primeLongRunningSession(elapsedSeconds: number, thresholdSeconds = 21600) {
  useTimerStore.setState({
    activeSession: {
      taskId: "task-1",
      taskTitle: "Fix rate limiter",
      startedAt: new Date(Date.now() - elapsedSeconds * 1000).toISOString(),
    },
    elapsedSeconds,
    longRunningThresholdSeconds: thresholdSeconds,
  });
}

beforeEach(() => {
  sessionStorage.clear();
  useTimerStore.getState().stopSession();
  useTimerStore.setState({
    activeSession: null,
    elapsedSeconds: 0,
    longRunningThresholdSeconds: null,
  });
});

describe("StaleTimerBanner", () => {
  it("renders nothing when no timer is running", () => {
    renderBanner();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("renders nothing while below the threshold", () => {
    primeLongRunningSession(60);
    renderBanner();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("warns once elapsed time reaches the threshold, naming the task", () => {
    primeLongRunningSession(21600);
    renderBanner();
    expect(screen.getByRole("alert")).toBeInTheDocument();
    expect(screen.getByText(/Fix rate limiter/)).toBeInTheDocument();
  });

  it("stops the timer from the banner action", async () => {
    let stoppedTaskId: string | null = null;
    server.use(
      http.post("*/tasks/:taskId/stop", ({ params }) => {
        stoppedTaskId = params.taskId as string;
        return HttpResponse.json({ id: "s1", ended_at: new Date().toISOString() });
      })
    );
    primeLongRunningSession(21600);
    renderBanner();

    await userEvent.click(screen.getByRole("button", { name: "Zatrzymaj timer" }));

    await waitFor(() => expect(stoppedTaskId).toBe("task-1"));
    await waitFor(() => expect(useTimerStore.getState().activeSession).toBeNull());
  });

  it("hides after dismissal and reappears after another full hour", async () => {
    primeLongRunningSession(6 * 3600);
    const { rerenderBanner } = renderBanner();
    expect(screen.getByRole("alert")).toBeInTheDocument();

    await userEvent.click(screen.getByLabelText("Zamknij"));
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();

    // Still within the dismissed hour: stays hidden across a re-render.
    primeLongRunningSession(6 * 3600 + 30 * 60);
    rerenderBanner();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();

    // A full extra hour has passed: the warning must resurface.
    primeLongRunningSession(7 * 3600 + 1);
    rerenderBanner();
    expect(screen.getByRole("alert")).toBeInTheDocument();
  });
});
