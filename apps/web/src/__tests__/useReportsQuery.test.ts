import { describe, it, expect } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { http, HttpResponse } from "msw";
import { server } from "./mocks/server";
import {
  useReportsQuery,
  getReportsRefetchInterval,
  type Report,
} from "@/features/reports/hooks/useReportsQuery";
import React from "react";

function wrapper() {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return ({ children }: { children: React.ReactNode }) =>
    React.createElement(QueryClientProvider, { client: qc }, children);
}

const baseReport: Omit<Report, "status"> = {
  id: "r1",
  type: "weekly_summary",
  format: "json",
  created_at: "2024-01-01",
  user_id: "u1",
};

describe("getReportsRefetchInterval", () => {
  it("polls every 3s when a report is pending", () => {
    expect(
      getReportsRefetchInterval([{ ...baseReport, status: "pending" }])
    ).toBe(3000);
  });

  it("polls every 3s when a report is generating", () => {
    expect(
      getReportsRefetchInterval([{ ...baseReport, status: "generating" }])
    ).toBe(3000);
  });

  it("stops polling once all reports are ready or failed", () => {
    expect(
      getReportsRefetchInterval([
        { ...baseReport, status: "ready" },
        { ...baseReport, id: "r2", status: "failed" },
      ])
    ).toBe(false);
  });

  it("stops polling when there is no data yet", () => {
    expect(getReportsRefetchInterval(undefined)).toBe(false);
  });
});

describe("useReportsQuery", () => {
  it("fetches the report list", async () => {
    server.use(
      http.get("*/reports", () =>
        HttpResponse.json({
          data: [{ ...baseReport, status: "generating" }],
          meta: { total: 1, limit: 50, offset: 0 },
        })
      )
    );

    const { result } = renderHook(() => useReportsQuery(), {
      wrapper: wrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.items[0].status).toBe("generating");
  });
});
