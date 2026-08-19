import { describe, it, expect } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { http, HttpResponse } from "msw";
import { server } from "./mocks/server";
import { useCycleTimeQuery } from "@/features/projects/hooks/useProjectsQuery";
import React from "react";

function wrapper() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return ({ children }: { children: React.ReactNode }) =>
    React.createElement(QueryClientProvider, { client: qc }, children);
}

describe("useCycleTimeQuery", () => {
  it("fetches and validates cycle-time data for a project", async () => {
    server.use(
      http.get("*/metrics/projects/p1/cycle-time", () =>
        HttpResponse.json({
          project_id: "p1",
          stages: [{ status: "backlog", average_hours: 2, sample_size: 3 }],
          stuck: [
            { task_id: "t1", title: "Fix bug", status: "review", hours_in_status: 12 },
          ],
        })
      )
    );
    const { result } = renderHook(() => useCycleTimeQuery("p1"), { wrapper: wrapper() });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.stages).toHaveLength(1);
    expect(result.current.data?.stuck[0]?.title).toBe("Fix bug");
  });

  it("is disabled when projectId is empty", () => {
    const { result } = renderHook(() => useCycleTimeQuery(""), { wrapper: wrapper() });
    expect(result.current.fetchStatus).toBe("idle");
  });
});
