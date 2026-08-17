import { describe, it, expect } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { http, HttpResponse } from "msw";
import { server } from "./mocks/server";
import { useMetricTrendsQuery } from "@/features/metrics/hooks/useMetricTrendsQuery";
import React from "react";

function createWrapper() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return ({ children }: { children: React.ReactNode }) =>
    React.createElement(QueryClientProvider, { client: queryClient }, children);
}

describe("useMetricTrendsQuery", () => {
  it("returns the weekly trend series", async () => {
    server.use(
      http.get("*/metrics/trends", () =>
        HttpResponse.json({
          period_from: "2026-02-16T00:00:00Z",
          period_to: "2026-08-10T00:00:00Z",
          weeks: 26,
          series: [
            {
              metric_key: "tasks_completed",
              points: [{ week_start: "2026-08-03", value: 2 }],
            },
          ],
        })
      )
    );

    const { result } = renderHook(() => useMetricTrendsQuery(26), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.data?.weeks).toBe(26);
    expect(result.current.data?.series[0]?.metric_key).toBe("tasks_completed");
    expect(result.current.data?.series[0]?.points[0]?.value).toBe(2);
  });

  it("isLoading is true initially", () => {
    server.use(
      http.get("*/metrics/trends", () =>
        HttpResponse.json({
          period_from: "2026-02-16T00:00:00Z",
          period_to: "2026-08-10T00:00:00Z",
          weeks: 12,
          series: [],
        })
      )
    );
    const { result } = renderHook(() => useMetricTrendsQuery(12), {
      wrapper: createWrapper(),
    });
    expect(result.current.isLoading).toBe(true);
  });
});
