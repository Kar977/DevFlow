import { describe, it, expect, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { http, HttpResponse } from "msw";
import { server } from "./mocks/server";
import { PullRequestListPage } from "@/features/pull-requests/pages/PullRequestListPage";
import { useOrgStore } from "@/shared/store/orgStore";

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={["/pull-requests"]}>
        <Routes>
          <Route path="/pull-requests" element={<PullRequestListPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  );
}

const samplePR = {
  id: "pr-1",
  repository_id: "repo-1",
  repository_full_name: "owner/repo",
  github_pr_id: 987654,
  number: 42,
  title: "Fix: something",
  author_login: "octocat",
  state: "open",
  created_at_github: "2026-06-01T10:00:00Z",
  merged_at: null,
  closed_at: null,
  first_review_at: null,
  html_url: "https://github.com/owner/repo/pull/42",
  last_synced_at: "2026-06-26T12:00:00Z",
};

beforeEach(() => {
  useOrgStore.setState({ activeOrgId: "org1" });
  server.use(
    http.get("*/repositories", () =>
      HttpResponse.json({ data: [] })
    )
  );
});

describe("PullRequestListPage", () => {
  it("requests the default newest-first sort", async () => {
    let capturedSort: string | null = null;
    server.use(
      http.get("*/pull-requests", ({ request }) => {
        capturedSort = new URL(request.url).searchParams.get("sort");
        return HttpResponse.json({ data: [], meta: { total: 0, limit: 50, offset: 0 } });
      })
    );

    renderPage();

    await waitFor(() => expect(capturedSort).toBe("newest"));
  });

  it("toggles to oldest-first when the age column header is clicked", async () => {
    const seenSorts: (string | null)[] = [];
    server.use(
      http.get("*/pull-requests", ({ request }) => {
        seenSorts.push(new URL(request.url).searchParams.get("sort"));
        return HttpResponse.json({
          data: [samplePR],
          meta: { total: 1, limit: 50, offset: 0 },
        });
      })
    );

    renderPage();
    await waitFor(() => expect(seenSorts).toContain("newest"));

    const header = await screen.findByRole("button", { name: /wiek/i });
    await userEvent.click(header);

    await waitFor(() => expect(seenSorts).toContain("oldest"));
  });
});
