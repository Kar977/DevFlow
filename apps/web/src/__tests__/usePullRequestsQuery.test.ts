import { describe, it, expect } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { http, HttpResponse } from "msw";
import { server } from "./mocks/server";
import {
  usePullRequestsQuery,
  usePullRequestDetailQuery,
} from "@/features/pull-requests/hooks/usePullRequestsQuery";
import React from "react";

const ORG_ID = "org-1";

function wrapper() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return ({ children }: { children: React.ReactNode }) =>
    React.createElement(QueryClientProvider, { client: qc }, children);
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

describe("usePullRequestsQuery", () => {
  it("fetches pull requests list with organization scope", async () => {
    let capturedOrgId: string | null = null;
    server.use(
      http.get("*/pull-requests", ({ request }) => {
        capturedOrgId = new URL(request.url).searchParams.get(
          "organization_id"
        );
        return HttpResponse.json({
          data: [samplePR],
          meta: { total: 1, limit: 50, offset: 0 },
        });
      })
    );
    const { result } = renderHook(() => usePullRequestsQuery(ORG_ID), {
      wrapper: wrapper(),
    });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.items).toHaveLength(1);
    expect(result.current.data?.items[0]?.title).toBe("Fix: something");
    expect(result.current.data?.items[0]?.repository_full_name).toBe(
      "owner/repo"
    );
    expect(capturedOrgId).toBe(ORG_ID);
  });

  it("returns empty list when no PRs", async () => {
    server.use(
      http.get("*/pull-requests", () =>
        HttpResponse.json({ data: [], meta: { total: 0, limit: 50, offset: 0 } })
      )
    );
    const { result } = renderHook(() => usePullRequestsQuery(ORG_ID), {
      wrapper: wrapper(),
    });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.items).toHaveLength(0);
  });

  it("is disabled without an active organization", () => {
    const { result } = renderHook(() => usePullRequestsQuery(null), {
      wrapper: wrapper(),
    });
    expect(result.current.fetchStatus).toBe("idle");
  });
});

describe("usePullRequestDetailQuery", () => {
  it("fetches PR detail with reviews", async () => {
    const detail = {
      ...samplePR,
      reviews: [
        {
          id: "r-1",
          reviewer_login: "reviewer1",
          state: "approved",
          submitted_at: "2026-06-02T10:00:00Z",
        },
      ],
    };
    server.use(
      http.get("*/pull-requests/pr-1", () => HttpResponse.json(detail))
    );
    const { result } = renderHook(
      () => usePullRequestDetailQuery(ORG_ID, "pr-1"),
      { wrapper: wrapper() }
    );
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.reviews).toHaveLength(1);
  });

  it("is disabled when no prId", () => {
    const { result } = renderHook(() => usePullRequestDetailQuery(ORG_ID, ""), {
      wrapper: wrapper(),
    });
    expect(result.current.fetchStatus).toBe("idle");
  });
});
