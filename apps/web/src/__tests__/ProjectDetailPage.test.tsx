import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { http, HttpResponse } from "msw";
import { server } from "./mocks/server";
import { ProjectDetailPage } from "@/features/projects/pages/ProjectDetailPage";
import { useOrgStore } from "@/shared/store/orgStore";

function renderPage(projectId = "p1") {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={[`/projects/${projectId}`]}>
        <Routes>
          <Route path="/projects/:projectId" element={<ProjectDetailPage />} />
          <Route path="/projects" element={<div>Lista projektów</div>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  );
}

beforeEach(() => {
  useOrgStore.setState({ activeOrgId: "org1" });

  server.use(
    http.get("*/projects", () =>
      HttpResponse.json({
        data: [
          { id: "p1", name: "Alpha", status: "active", org_id: "org1", created_by: "u1", created_at: "2024-01-01", updated_at: "2024-01-01" },
        ],
        meta: { total: 1, limit: 50, offset: 0 },
      })
    ),
    http.get("*/metrics/projects/p1", () =>
      HttpResponse.json({ total_tasks: 3, completed_tasks: 1, total_hours: 5.5 })
    ),
    http.get("*/metrics/projects/p1/cycle-time", () =>
      HttpResponse.json({
        project_id: "p1",
        stages: [{ status: "in_progress", average_hours: 4, sample_size: 2 }],
        stuck: [],
      })
    ),
    http.get("*/tasks", () =>
      HttpResponse.json({
        data: [
          { id: "t1", title: "Fix bug", status: "todo", priority: "high", project_id: "p1", created_by: "u1", created_at: "2024-01-01", updated_at: "2024-01-01" },
        ],
        meta: { total: 1, limit: 50, offset: 0 },
      })
    )
  );
});

describe("ProjectDetailPage", () => {
  it("shows the project name, metrics and its tasks", async () => {
    renderPage();

    await waitFor(() => expect(screen.getByText("Alpha")).toBeInTheDocument());
    expect(await screen.findByText("3")).toBeInTheDocument();
    expect(await screen.findByText("Fix bug")).toBeInTheDocument();
    // Chart internals (recharts) aren't mocked at the page level — that's
    // covered by CycleTimePanel.test.tsx — this just checks it's mounted.
    expect(await screen.findByText("Cycle time per etap")).toBeInTheDocument();
  });

  it("archives the project and navigates back to the list", async () => {
    server.use(
      http.delete("*/projects/p1", () => new HttpResponse(null, { status: 204 }))
    );
    vi.spyOn(window, "confirm").mockReturnValue(true);

    renderPage();

    const archiveButton = await screen.findByRole("button", { name: /archiwizuj/i });
    await userEvent.click(archiveButton);

    await waitFor(() => expect(screen.getByText("Lista projektów")).toBeInTheDocument());
  });
});
