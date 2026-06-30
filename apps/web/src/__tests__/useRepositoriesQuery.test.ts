import { describe, it, expect } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { http, HttpResponse } from "msw";
import { server } from "./mocks/server";
import { useRepositoriesQuery } from "@/features/repositories/hooks/useRepositoriesQuery";
import React from "react";

function wrapper() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return ({ children }: { children: React.ReactNode }) =>
    React.createElement(QueryClientProvider, { client: qc }, children);
}

describe("useRepositoriesQuery", () => {
  it("fetches repositories list", async () => {
    server.use(
      http.get("*/repositories", () =>
        HttpResponse.json({
          items: [{ full_name: "owner/repo", pr_count: 5 }],
        })
      )
    );
    const { result } = renderHook(() => useRepositoriesQuery(), {
      wrapper: wrapper(),
    });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.items).toHaveLength(1);
    expect(result.current.data?.items[0]?.full_name).toBe("owner/repo");
    expect(result.current.data?.items[0]?.pr_count).toBe(5);
  });

  it("returns empty list when no repos", async () => {
    server.use(
      http.get("*/repositories", () => HttpResponse.json({ items: [] }))
    );
    const { result } = renderHook(() => useRepositoriesQuery(), {
      wrapper: wrapper(),
    });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.items).toHaveLength(0);
  });
});
