import { describe, it, expect, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { http, HttpResponse } from "msw";
import { server } from "./mocks/server";
import { OverdueTasksBanner } from "@/features/tasks/components/OverdueTasksBanner";
import { useOrgStore } from "@/shared/store/orgStore";

function renderBanner() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <OverdueTasksBanner />
      </MemoryRouter>
    </QueryClientProvider>
  );
}

function makeTask(title: string) {
  return {
    id: title,
    title,
    status: "todo",
    priority: "medium",
    project_id: "p1",
    created_by: "u1",
    created_at: "2024-01-01",
    updated_at: "2024-01-01",
    due_date: "2026-01-01T23:59:59Z",
  };
}

beforeEach(() => {
  sessionStorage.clear();
  useOrgStore.setState({ activeOrgId: "org1" });
});

describe("OverdueTasksBanner", () => {
  it("renders nothing when there is no active organization", () => {
    useOrgStore.setState({ activeOrgId: null });
    renderBanner();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("renders nothing when there are no overdue tasks", async () => {
    server.use(
      http.get("*/tasks/overdue", () =>
        HttpResponse.json({ data: [], meta: { total: 0, limit: 5, offset: 0 } })
      )
    );
    renderBanner();
    await waitFor(() => expect(screen.queryByRole("alert")).not.toBeInTheDocument());
  });

  it("shows the overdue count and task titles", async () => {
    server.use(
      http.get("*/tasks/overdue", () =>
        HttpResponse.json({
          data: [makeTask("Fix bug"), makeTask("Write docs")],
          meta: { total: 2, limit: 5, offset: 0 },
        })
      )
    );
    renderBanner();
    await waitFor(() =>
      expect(screen.getByText(/masz 2 zadania po terminie/i)).toBeInTheDocument()
    );
    expect(screen.getByText("Fix bug")).toBeInTheDocument();
    expect(screen.getByText("Write docs")).toBeInTheDocument();
  });

  it("sends organization_id and the banner limit", async () => {
    let captured: URLSearchParams | null = null;
    server.use(
      http.get("*/tasks/overdue", ({ request }) => {
        captured = new URL(request.url).searchParams;
        return HttpResponse.json({ data: [], meta: { total: 0, limit: 5, offset: 0 } });
      })
    );
    renderBanner();
    await waitFor(() => expect(captured).not.toBeNull());
    expect(captured!.get("organization_id")).toBe("org1");
    expect(captured!.get("limit")).toBe("5");
  });

  it("hides after dismissal and reappears when the count grows", async () => {
    server.use(
      http.get("*/tasks/overdue", () =>
        HttpResponse.json({
          data: [makeTask("Fix bug")],
          meta: { total: 1, limit: 5, offset: 0 },
        })
      )
    );
    renderBanner();
    await waitFor(() => expect(screen.getByRole("alert")).toBeInTheDocument());

    await userEvent.click(screen.getByLabelText("Zamknij"));
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();

    server.use(
      http.get("*/tasks/overdue", () =>
        HttpResponse.json({
          data: [makeTask("Fix bug"), makeTask("Write docs")],
          meta: { total: 2, limit: 5, offset: 0 },
        })
      )
    );
    // Re-render as a fresh mount to simulate the query refetching with a
    // higher total (e.g. after navigating to another page and back).
    renderBanner();
    await waitFor(() =>
      expect(screen.getAllByRole("alert").length).toBeGreaterThan(0)
    );
  });
});
