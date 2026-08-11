import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Toaster } from "sonner";
import { TimerButton } from "@/features/tasks/components/TimerButton";
import { useTimerStore } from "@/shared/store/timerStore";
import type { Task } from "@/features/tasks/hooks/useTasksQuery";

const mockTask: Task = {
  id: "task-1",
  title: "Fix bug",
  status: "in_progress",
  priority: "high",
  project_id: "p1",
  created_by: "u1",
  created_at: "2024-01-01",
  updated_at: "2024-01-01",
};

const { mockStart, mockStop, mockSwitchTo } = vi.hoisted(() => ({
  mockStart: vi.fn(),
  mockStop: vi.fn(),
  mockSwitchTo: vi.fn(),
}));

vi.mock("@/features/tasks/hooks/useTimerMutation", () => ({
  useTimerMutation: () => ({
    start: mockStart,
    stop: mockStop,
    switchTo: mockSwitchTo,
    isStarting: false,
    isStopping: false,
  }),
}));

/** A fake Axios 409 error, shaped just enough for `axios.isAxiosError` (used
 * by `isConflictError`) to recognize it. */
function conflictError() {
  return Object.assign(new Error("Conflict"), {
    isAxiosError: true,
    response: { status: 409 },
  });
}

function renderButton(task: Task) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <Toaster />
      <TimerButton task={task} />
    </QueryClientProvider>
  );
}

beforeEach(() => {
  useTimerStore.setState({ activeSession: null, elapsedSeconds: 0 });
  mockStart.mockClear();
  mockStop.mockClear();
  mockSwitchTo.mockClear();
});

describe("TimerButton", () => {
  it("shows Start when no active session", () => {
    renderButton(mockTask);
    expect(screen.getByRole("button", { name: /start/i })).toBeInTheDocument();
  });

  it("shows Stop when this task is active", () => {
    useTimerStore.setState({
      activeSession: { taskId: "task-1", taskTitle: "Fix bug", startedAt: new Date().toISOString() },
      elapsedSeconds: 65,
    });
    renderButton(mockTask);
    expect(screen.getByRole("button", { name: /stop/i })).toBeInTheDocument();
  });

  it("shows Start (enabled) when another task is active", () => {
    // Previously this button was disabled with no explanation whenever any
    // other task's timer was running, which looked broken. Clicking now
    // surfaces the 409 via a toast with a "stop and switch" action instead
    // of silently doing nothing — see the 409 tests below for that flow.
    useTimerStore.setState({
      activeSession: { taskId: "other-task", taskTitle: "Other", startedAt: new Date().toISOString() },
      elapsedSeconds: 10,
    });
    renderButton(mockTask);
    const btn = screen.getByRole("button", { name: /start/i });
    expect(btn).not.toBeDisabled();
  });

  it("on a 409, shows a toast naming the blocking task with a switch action", async () => {
    useTimerStore.setState({
      activeSession: { taskId: "other-task", taskTitle: "Other task", startedAt: new Date().toISOString() },
      elapsedSeconds: 10,
    });
    renderButton(mockTask);

    await userEvent.click(screen.getByRole("button", { name: /^start$/i }));
    expect(mockStart).toHaveBeenCalledTimes(1);
    const options = mockStart.mock.calls[0]?.[1] as { onError: (e: unknown) => void };
    options.onError(conflictError());

    expect(await screen.findByText(/Timer już działa: "Other task"/)).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: /zatrzymaj i przełącz/i }));
    expect(mockSwitchTo).toHaveBeenCalledWith("other-task");
  });

  it("on a 409 with no locally-known blocking task, shows a generic message", async () => {
    renderButton(mockTask); // no activeSession set at all
    await userEvent.click(screen.getByRole("button", { name: /^start$/i }));
    const options = mockStart.mock.calls[0]?.[1] as { onError: (e: unknown) => void };
    options.onError(conflictError());

    expect(
      await screen.findByText("Masz już uruchomiony timer na innym zadaniu.")
    ).toBeInTheDocument();
  });
});
