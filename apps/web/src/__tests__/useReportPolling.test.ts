import { describe, it, expect } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { http, HttpResponse } from "msw";
import { server } from "./mocks/server";
import { useReportPolling } from "@/features/reports/hooks/useReportsQuery";
import React from "react";

function wrapper() {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return ({ children }: { children: React.ReactNode }) =>
    React.createElement(QueryClientProvider, { client: qc }, children);
}

describe("useReportPolling", () => {
  it("is disabled when reportId is null", () => {
    const { result } = renderHook(() => useReportPolling(null), { wrapper: wrapper() });
    expect(result.current.fetchStatus).toBe("idle");
  });

  it("fetches report status when reportId provided", async () => {
    server.use(
      http.get("*/reports/r1", () =>
        HttpResponse.json({ id: "r1", status: "ready", type: "weekly_summary", format: "json", created_at: "2024-01-01", user_id: "u1" })
      )
    );
    const { result } = renderHook(() => useReportPolling("r1"), { wrapper: wrapper() });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.status).toBe("ready");
  });

  it("returns generating status while report not ready", async () => {
    server.use(
      http.get("*/reports/r2", () =>
        HttpResponse.json({ id: "r2", status: "generating", type: "weekly_summary", format: "json", created_at: "2024-01-01", user_id: "u1" })
      )
    );
    const { result } = renderHook(() => useReportPolling("r2"), { wrapper: wrapper() });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.status).toBe("generating");
  });
});
