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
        HttpResponse.json({ connected: true, github_login: "octocat", github_avatar_url: null })
      )
    );
    const { result } = renderHook(() => useGitHubStatus(), { wrapper: wrapper() });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.connected).toBe(true);
    expect(result.current.data?.github_login).toBe("octocat");
  });

  it("returns not connected status", async () => {
    server.use(
      http.get("*/integrations/github/status", () =>
        HttpResponse.json({ connected: false })
      )
    );
    const { result } = renderHook(() => useGitHubStatus(), { wrapper: wrapper() });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.connected).toBe(false);
  });
});
