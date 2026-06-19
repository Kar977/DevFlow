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
    server.use(
      http.get("*/metrics/summary", () =>
        HttpResponse.json({
          completed_tasks: { value: 5, prev_value: 3, delta_pct: 66.7 },
          active_hours: { value: 12, prev_value: 10, delta_pct: 20.0 },
        })
      ),
      http.get("*/metrics/velocity", () =>
        HttpResponse.json({
          weeks: [{ week: "2026-W24", tasks_closed: 5 }],
          trend_pct: 10.0,
        })
      )
    );

    const { result } = renderHook(() => useDashboardData(), { wrapper: createWrapper() });

    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.summary?.completed_tasks.value).toBe(5);
    expect(result.current.velocity?.weeks).toHaveLength(1);
  });

  it("isLoading is true initially", () => {
    server.use(
      http.get("*/metrics/summary", () => HttpResponse.json({})),
      http.get("*/metrics/velocity", () => HttpResponse.json({}))
    );
    const { result } = renderHook(() => useDashboardData(), { wrapper: createWrapper() });
    expect(result.current.isLoading).toBe(true);
  });
});
