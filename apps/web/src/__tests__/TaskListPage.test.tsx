import { describe, it, expect, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { http, HttpResponse } from "msw";
import { server } from "./mocks/server";
import { TaskListPage } from "@/features/tasks/pages/TaskListPage";
import { useOrgStore } from "@/shared/store/orgStore";

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={["/tasks"]}>
        <Routes>
          <Route path="/tasks" element={<TaskListPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  );
}

const project = {
  id: "p1",
  name: "API",
  status: "active",
  org_id: "org1",
  created_by: "u1",
  created_at: "2024-01-01",
  updated_at: "2024-01-01",
};

function makeTask(overrides: Record<string, unknown>) {
  return {
    id: "t-" + Math.random(),
    title: "Task",
    status: "todo",
    priority: "medium",
    project_id: "p1",
    created_by: "u1",
    created_at: "2024-01-01",
    updated_at: "2024-01-01",
    ...overrides,
  };
}

beforeEach(() => {
  useOrgStore.setState({ activeOrgId: "org1" });
  server.use(
    http.get("*/projects", () =>
      HttpResponse.json({ data: [project], meta: { total: 1, limit: 50, offset: 0 } })
    ),
    http.get("*/organizations/org1/members", () => HttpResponse.json({ data: [] }))
  );
});

describe("TaskListPage", () => {
  it("hides non-overdue tasks when 'Tylko przeterminowane' is checked", async () => {
    const overdueTask = makeTask({
      id: "overdue-1",
      title: "Overdue task",
      due_date: new Date(Date.now() - 86_400_000).toISOString(),
    });
    const futureTask = makeTask({
      id: "future-1",
      title: "Future task",
      due_date: new Date(Date.now() + 86_400_000).toISOString(),
    });
    server.use(
      http.get("*/tasks", () =>
        HttpResponse.json({
          data: [overdueTask, futureTask],
          meta: { total: 2, limit: 50, offset: 0 },
        })
      )
    );

    renderPage();

    await waitFor(() => expect(screen.getByText("Overdue task")).toBeInTheDocument());
    expect(screen.getByText("Future task")).toBeInTheDocument();

    await userEvent.click(screen.getByLabelText("Tylko przeterminowane"));

    expect(screen.getByText("Overdue task")).toBeInTheDocument();
    expect(screen.queryByText("Future task")).not.toBeInTheDocument();
  });
});
