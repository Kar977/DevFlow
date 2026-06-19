import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
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

vi.mock("@/features/tasks/hooks/useTimerMutation", () => ({
  useTimerMutation: () => ({
    start: vi.fn(),
    stop: vi.fn(),
    isStarting: false,
    isStopping: false,
  }),
}));

function renderButton(task: Task) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <TimerButton task={task} />
    </QueryClientProvider>
  );
}

beforeEach(() => {
  useTimerStore.setState({ activeSession: null, elapsedSeconds: 0 });
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

  it("shows Start (disabled) when another task is active", () => {
    useTimerStore.setState({
      activeSession: { taskId: "other-task", taskTitle: "Other", startedAt: new Date().toISOString() },
      elapsedSeconds: 10,
    });
    renderButton(mockTask);
    const btn = screen.getByRole("button", { name: /start/i });
    expect(btn).toBeDisabled();
  });
});
