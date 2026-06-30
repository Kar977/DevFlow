import { describe, it, expect } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { http, HttpResponse } from "msw";
import { server } from "./mocks/server";
import { useGitHubStatus } from "@/features/github/hooks/useGitHubStatus";
import React from "react";

function wrapper() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return ({ children }: { children: React.ReactNode }) =>
    React.createElement(QueryClientProvider, { client: qc }, children);
}

describe("useGitHubStatus", () => {
  it("returns connected status when github is linked", async () => {
    server.use(
      http.get("*/integrations/github/status", () =>
        HttpResponse.json({
          id: "uuid-1",
          github_user_id: "4242",
          github_login: "octocat",
          scopes: "read:user",
          connected_at: "2026-01-01T00:00:00Z",
        })
      )
    );
    const { result } = renderHook(() => useGitHubStatus(), { wrapper: wrapper() });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.connected).toBe(true);
    expect(result.current.data?.github_login).toBe("octocat");
  });

  it("returns not connected status when api returns null", async () => {
    server.use(
      http.get("*/integrations/github/status", () => HttpResponse.json(null))
    );
    const { result } = renderHook(() => useGitHubStatus(), { wrapper: wrapper() });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.connected).toBe(false);
    expect(result.current.data?.github_login).toBeNull();
  });
});
