import { describe, it, expect } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { http, HttpResponse } from "msw";
import { server } from "./mocks/server";
import { useDashboardData } from "@/features/dashboard/hooks/useDashboardData";
import React from "react";

function createWrapper() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return ({ children }: { children: React.ReactNode }) =>
    React.createElement(QueryClientProvider, { client: queryClient }, children);
}

describe("useDashboardData", () => {
  it("returns summary and velocity data", async () => {
    // Shapes below mirror the real backend contract (core/schemas/metrics):
    // SummaryResponse.tasks_completed (not completed_tasks), and
    // VelocityResponse.weeks is a float period length, not a per-week array.
    server.use(
      http.get("*/metrics/summary", () =>
        HttpResponse.json({
          period_from: "2026-07-11T00:00:00Z",
          period_to: "2026-08-10T00:00:00Z",
          tasks_completed: { value: 5, prev_value: 3, delta_pct: 66.7 },
          active_hours: { value: 12, prev_value: 10, delta_pct: 20.0 },
        })
      ),
      http.get("*/metrics/velocity", () =>
        HttpResponse.json({
          period_from: "2026-07-11T00:00:00Z",
          period_to: "2026-08-10T00:00:00Z",
          total_done: 5,
          weeks: 4.29,
          average_per_week: 1.17,
          trend_pct: 10.0,
          weekly: [{ week_start: "2026-08-03", tasks_completed: 5 }],
        })
      )
    );

    const { result } = renderHook(() => useDashboardData(), { wrapper: createWrapper() });

    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.summary?.tasks_completed.value).toBe(5);
    expect(result.current.velocity?.total_done).toBe(5);
    expect(result.current.velocity?.weekly).toHaveLength(1);
  });

  it("isLoading is true initially", () => {
    server.use(
      http.get("*/metrics/summary", () =>
        HttpResponse.json({
          period_from: "2026-07-11T00:00:00Z",
          period_to: "2026-08-10T00:00:00Z",
          tasks_completed: { value: 0, prev_value: 0, delta_pct: null },
          active_hours: { value: 0, prev_value: 0, delta_pct: null },
        })
      ),
      http.get("*/metrics/velocity", () =>
        HttpResponse.json({
          period_from: "2026-07-11T00:00:00Z",
          period_to: "2026-08-10T00:00:00Z",
          total_done: 0,
          weeks: 4.29,
          average_per_week: 0,
          trend_pct: null,
          weekly: [],
        })
      )
    );
    const { result } = renderHook(() => useDashboardData(), { wrapper: createWrapper() });
    expect(result.current.isLoading).toBe(true);
  });
});
