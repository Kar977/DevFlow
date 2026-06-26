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

function wrapper() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return ({ children }: { children: React.ReactNode }) =>
    React.createElement(QueryClientProvider, { client: qc }, children);
}

const samplePR = {
  id: "pr-1",
  github_pr_id: 42,
  github_repo_full_name: "owner/repo",
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
  it("fetches pull requests list", async () => {
    server.use(
      http.get("*/pull-requests", () =>
        HttpResponse.json({ items: [samplePR], total: 1 })
      )
    );
    const { result } = renderHook(() => usePullRequestsQuery(), {
      wrapper: wrapper(),
    });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.items).toHaveLength(1);
    expect(result.current.data?.items[0]?.title).toBe("Fix: something");
  });

  it("returns empty list when no PRs", async () => {
    server.use(
      http.get("*/pull-requests", () =>
        HttpResponse.json({ items: [], total: 0 })
      )
    );
    const { result } = renderHook(() => usePullRequestsQuery(), {
      wrapper: wrapper(),
    });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.items).toHaveLength(0);
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
    const { result } = renderHook(() => usePullRequestDetailQuery("pr-1"), {
      wrapper: wrapper(),
    });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.reviews).toHaveLength(1);
  });

  it("is disabled when no prId", () => {
    const { result } = renderHook(() => usePullRequestDetailQuery(""), {
      wrapper: wrapper(),
    });
    expect(result.current.fetchStatus).toBe("idle");
  });
});
