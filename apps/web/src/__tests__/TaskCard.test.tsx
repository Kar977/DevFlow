import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { http, HttpResponse } from "msw";
import { server } from "./mocks/server";
import { TaskCard } from "@/features/tasks/components/TaskCard";
import { useTimerStore } from "@/shared/store/timerStore";
import { useOrgStore } from "@/shared/store/orgStore";
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
  useOrgStore.setState({ activeOrgId: "org-1" });
  server.use(
    http.get("*/organizations/org-1/members", () =>
      HttpResponse.json({ data: [] })
    )
  );
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

  it("shows an assignee badge when the task has a matching org member", async () => {
    server.use(
      http.get("*/organizations/org-1/members", () =>
        HttpResponse.json({
          data: [
            {
              id: "mem-1",
              org_id: "org-1",
              user_id: "user-42",
              role: "member",
              joined_at: "2024-01-01T00:00:00Z",
              display_name: "Jan Kowalski",
            },
          ],
        })
      )
    );

    renderCard({ ...baseTask, assignee_id: "user-42" });

    await waitFor(() =>
      expect(screen.getByText("👤 Jan Kowalski")).toBeInTheDocument()
    );
  });

  it("shows no assignee badge when the task is unassigned", () => {
    renderCard(baseTask);
    expect(screen.queryByText(/👤/)).not.toBeInTheDocument();
  });

  it("shows no due-date badge when the task has none", () => {
    renderCard(baseTask);
    expect(screen.queryByText(/📅/)).not.toBeInTheDocument();
  });

  it("shows a due-date badge without overdue styling for a future due date", () => {
    const future = new Date(Date.now() + 86_400_000).toISOString();
    renderCard({ ...baseTask, due_date: future });
    const badge = screen.getByText(/📅/);
    expect(badge).toBeInTheDocument();
    expect(badge.className).toContain("bg-slate-100");
  });

  it("shows overdue styling for a past due date on an open task", () => {
    const past = new Date(Date.now() - 86_400_000).toISOString();
    renderCard({ ...baseTask, due_date: past });
    const badge = screen.getByText(/📅/);
    expect(badge.className).toContain("bg-red-100");
  });

  it("does not show overdue styling for a past due date on a done task", () => {
    const past = new Date(Date.now() - 86_400_000).toISOString();
    renderCard({ ...baseTask, due_date: past, status: "done" });
    const badge = screen.getByText(/📅/);
    expect(badge.className).toContain("bg-slate-100");
  });
});
