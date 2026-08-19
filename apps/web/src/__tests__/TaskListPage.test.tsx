import { describe, it, expect, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { http, HttpResponse } from "msw";
import { server } from "./mocks/server";
import { TaskListPage } from "@/features/tasks/pages/TaskListPage";
import { useOrgStore } from "@/shared/store/orgStore";
import { useProjectStore } from "@/shared/store/projectStore";
import { useTaskFilterStore } from "@/shared/store/taskFilterStore";

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
  localStorage.clear();
  useOrgStore.setState({ activeOrgId: "org1" });
  useProjectStore.setState({ activeProjectIdByOrg: {} });
  useTaskFilterStore.setState({
    status: "all",
    assigneeIdByOrg: {},
    sprintFilterByOrg: {},
  });
  server.use(
    http.get("*/projects", () =>
      HttpResponse.json({ data: [project], meta: { total: 1, limit: 50, offset: 0 } })
    ),
    http.get("*/organizations/org1/members", () => HttpResponse.json({ data: [] })),
    http.get("*/organizations/org1/sprints", () => HttpResponse.json({ data: [] }))
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

  describe("project selection persistence", () => {
    const projectA = { ...project, id: "p-a", name: "Project A" };
    const projectB = { ...project, id: "p-b", name: "Project B" };

    function serveTasksAndCaptureProjectId(capture: { value: string | null }) {
      server.use(
        http.get("*/projects", () =>
          HttpResponse.json({
            data: [projectA, projectB],
            meta: { total: 2, limit: 50, offset: 0 },
          })
        ),
        http.get("*/tasks", ({ request }) => {
          capture.value = new URL(request.url).searchParams.get("project_id");
          return HttpResponse.json({ data: [], meta: { total: 0, limit: 50, offset: 0 } });
        })
      );
    }

    it("honors a previously selected project even when it is not the first in the list", async () => {
      useProjectStore.setState({ activeProjectIdByOrg: { org1: "p-b" } });
      const captured = { value: null as string | null };
      serveTasksAndCaptureProjectId(captured);

      renderPage();

      await waitFor(() => expect(captured.value).toBe("p-b"));
    });

    it("falls back to the first project when the stored id no longer exists", async () => {
      useProjectStore.setState({ activeProjectIdByOrg: { org1: "does-not-exist" } });
      const captured = { value: null as string | null };
      serveTasksAndCaptureProjectId(captured);

      renderPage();

      await waitFor(() => expect(captured.value).toBe("p-a"));
      // The fallback must also be written back to the store, so navigating
      // away and back keeps showing "Project A" instead of re-defaulting.
      await waitFor(() =>
        expect(useProjectStore.getState().activeProjectIdByOrg.org1).toBe("p-a")
      );
    });

    it("keeps the selection when the page unmounts and remounts", async () => {
      const captured = { value: null as string | null };
      serveTasksAndCaptureProjectId(captured);

      const { unmount } = renderPage();
      await waitFor(() => expect(captured.value).toBe("p-a"));

      unmount();
      captured.value = null;
      renderPage();

      await waitFor(() => expect(captured.value).toBe("p-a"));
    });
  });

  describe("status/assignee filter persistence", () => {
    function captureTaskParams(capture: { status: string | null; assignee: string | null }) {
      server.use(
        http.get("*/tasks", ({ request }) => {
          const params = new URL(request.url).searchParams;
          capture.status = params.get("status");
          capture.assignee = params.get("assignee_id");
          return HttpResponse.json({ data: [], meta: { total: 0, limit: 50, offset: 0 } });
        })
      );
    }

    it("honors a previously selected status filter across remounts", async () => {
      useTaskFilterStore.setState({ status: "done", assigneeIdByOrg: {} });
      const captured = { status: null as string | null, assignee: null as string | null };
      captureTaskParams(captured);

      renderPage();

      await waitFor(() => expect(captured.status).toBe("done"));
    });

    it("honors a previously selected assignee filter, scoped to the active org", async () => {
      useTaskFilterStore.setState({
        status: "all",
        assigneeIdByOrg: { org1: "user-1", "other-org": "user-2" },
      });
      const captured = { status: null as string | null, assignee: null as string | null };
      captureTaskParams(captured);

      renderPage();

      await waitFor(() => expect(captured.assignee).toBe("user-1"));
    });

    it("keeps status and assignee selections when the page unmounts and remounts", async () => {
      useTaskFilterStore.setState({ status: "in_progress", assigneeIdByOrg: { org1: "user-1" } });
      const captured = { status: null as string | null, assignee: null as string | null };
      captureTaskParams(captured);

      const { unmount } = renderPage();
      await waitFor(() => expect(captured.status).toBe("in_progress"));
      expect(captured.assignee).toBe("user-1");

      unmount();
      captured.status = null;
      captured.assignee = null;
      renderPage();

      await waitFor(() => expect(captured.status).toBe("in_progress"));
      expect(captured.assignee).toBe("user-1");
    });
  });
});
