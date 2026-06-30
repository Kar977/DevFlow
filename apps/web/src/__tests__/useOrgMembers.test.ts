import { describe, it, expect } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { http, HttpResponse } from "msw";
import React from "react";
import { server } from "./mocks/server";
import { useOrgMembersQuery } from "@/features/organizations/hooks/useOrgMembers";

function wrapper() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return ({ children }: { children: React.ReactNode }) =>
    React.createElement(QueryClientProvider, { client: qc }, children);
}

describe("useOrgMembersQuery", () => {
  it("fetches members for a given org", async () => {
    const member = {
      id: "mem-1",
      org_id: "org-1",
      user_id: "user-1",
      role: "owner",
      joined_at: "2024-01-01T00:00:00Z",
    };
    server.use(
      http.get("*/organizations/org-1/members", () =>
        HttpResponse.json([member])
      )
    );

    const { result } = renderHook(() => useOrgMembersQuery("org-1"), {
      wrapper: wrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toHaveLength(1);
    expect(result.current.data?.[0]?.user_id).toBe("user-1");
  });

  it("is disabled when orgId is null", () => {
    const { result } = renderHook(() => useOrgMembersQuery(null), {
      wrapper: wrapper(),
    });
    expect(result.current.fetchStatus).toBe("idle");
  });
});
