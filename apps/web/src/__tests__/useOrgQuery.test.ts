import { describe, it, expect } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { http, HttpResponse } from "msw";
import React from "react";
import { server } from "./mocks/server";
import { useOrgQuery } from "@/features/organizations/hooks/useOrgsQuery";

function wrapper() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return ({ children }: { children: React.ReactNode }) =>
    React.createElement(QueryClientProvider, { client: qc }, children);
}

const validOrg = {
  id: "11111111-1111-1111-1111-111111111111",
  name: "Acme",
  slug: "acme",
  description: "A company",
  created_by: "22222222-2222-2222-2222-222222222222",
  created_at: "2024-01-01T00:00:00Z",
  updated_at: "2024-01-01T00:00:00Z",
};

describe("useOrgQuery", () => {
  it("fetches and parses full organization detail, including description", async () => {
    server.use(
      http.get("*/organizations/11111111-1111-1111-1111-111111111111", () =>
        HttpResponse.json(validOrg)
      )
    );

    const { result } = renderHook(
      () => useOrgQuery("11111111-1111-1111-1111-111111111111"),
      { wrapper: wrapper() }
    );

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.description).toBe("A company");
  });

  it("is disabled when orgId is null", () => {
    const { result } = renderHook(() => useOrgQuery(null), { wrapper: wrapper() });
    expect(result.current.fetchStatus).toBe("idle");
  });

  it("rejects a malformed payload instead of returning bad data", async () => {
    server.use(
      http.get("*/organizations/11111111-1111-1111-1111-111111111111", () =>
        HttpResponse.json({ id: "not-a-uuid", name: "Acme" })
      )
    );

    const { result } = renderHook(
      () => useOrgQuery("11111111-1111-1111-1111-111111111111"),
      { wrapper: wrapper() }
    );

    await waitFor(() => expect(result.current.isError).toBe(true));
  });
});
