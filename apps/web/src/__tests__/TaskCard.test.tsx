import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { TaskCard } from "@/features/tasks/components/TaskCard";
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
};

vi.mock("@/features/tasks/hooks/useTimerMutation", () => ({
  useTimerMutation: () => ({
    start: vi.fn(),
    stop: vi.fn(),
    isStarting: false,
    isStopping: false,
  }),
}));

function renderCard(task: Task) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <TaskCard task={task} />
    </QueryClientProvider>
  );
}

beforeEach(() => {
  useTimerStore.setState({ activeSession: null, elapsedSeconds: 0 });
});

describe("TaskCard", () => {
  it("does not show a tracked-time badge when nothing has been tracked yet", () => {
    renderCard(baseTask);
    expect(screen.queryByText(/⏱/)).not.toBeInTheDocument();
  });

  it("shows the accumulated tracked time across past sessions", () => {
    renderCard({ ...baseTask, tracked_seconds: 90 * 60 });
    expect(screen.getByText("⏱ 1h 30m")).toBeInTheDocument();
  });
});
