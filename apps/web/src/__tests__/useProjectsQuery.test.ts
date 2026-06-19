import { describe, it, expect } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { http, HttpResponse } from "msw";
import { server } from "./mocks/server";
import { useProjectsQuery } from "@/features/projects/hooks/useProjectsQuery";
import { useOrgStore } from "@/shared/store/orgStore";
import React from "react";

function wrapper() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return ({ children }: { children: React.ReactNode }) =>
    React.createElement(QueryClientProvider, { client: qc }, children);
}

describe("useProjectsQuery", () => {
  it("fetches projects for active org", async () => {
    useOrgStore.setState({ activeOrgId: "org-1" });
    server.use(
      http.get("*/projects", () =>
        HttpResponse.json({
          items: [{ id: "p1", name: "DevFlow", status: "active", org_id: "org-1", created_by: "u1", created_at: "2024-01-01", updated_at: "2024-01-01" }],
          total: 1,
        })
      )
    );
    const { result } = renderHook(() => useProjectsQuery(), { wrapper: wrapper() });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.items).toHaveLength(1);
    expect(result.current.data?.items[0]?.name).toBe("DevFlow");
  });

  it("is disabled when no active org", () => {
    useOrgStore.setState({ activeOrgId: null });
    const { result } = renderHook(() => useProjectsQuery(), { wrapper: wrapper() });
    expect(result.current.fetchStatus).toBe("idle");
  });
});
