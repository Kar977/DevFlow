import { describe, it, expect } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { http, HttpResponse } from "msw";
import { server } from "./mocks/server";
import { useRepositoriesQuery } from "@/features/repositories/hooks/useRepositoriesQuery";
import React from "react";

const ORG_ID = "org-1";

function wrapper() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return ({ children }: { children: React.ReactNode }) =>
    React.createElement(QueryClientProvider, { client: qc }, children);
}

const sampleRepo = {
  id: "repo-1",
  github_installation_id: "inst-1",
  full_name: "owner/repo",
  private: false,
  default_branch: "main",
  tracked: true,
  last_synced_at: "2026-06-26T12:00:00Z",
};

describe("useRepositoriesQuery", () => {
  it("fetches repositories list with organization scope", async () => {
    let capturedOrgId: string | null = null;
    server.use(
      http.get("*/repositories", ({ request }) => {
        capturedOrgId = new URL(request.url).searchParams.get(
          "organization_id"
        );
        return HttpResponse.json({ data: [sampleRepo] });
      })
    );
    const { result } = renderHook(() => useRepositoriesQuery(ORG_ID), {
      wrapper: wrapper(),
    });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.items).toHaveLength(1);
    expect(result.current.data?.items[0]?.full_name).toBe("owner/repo");
    expect(result.current.data?.items[0]?.tracked).toBe(true);
    expect(capturedOrgId).toBe(ORG_ID);
  });

  it("returns empty list when no repos", async () => {
    server.use(
      http.get("*/repositories", () => HttpResponse.json({ data: [] }))
    );
    const { result } = renderHook(() => useRepositoriesQuery(ORG_ID), {
      wrapper: wrapper(),
    });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.items).toHaveLength(0);
  });

  it("is disabled without an active organization", () => {
    const { result } = renderHook(() => useRepositoriesQuery(null), {
      wrapper: wrapper(),
    });
    expect(result.current.fetchStatus).toBe("idle");
  });
});
