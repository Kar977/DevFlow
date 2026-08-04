import { describe, it, expect } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { http, HttpResponse } from "msw";
import { server } from "./mocks/server";
import { useTasksQuery } from "@/features/tasks/hooks/useTasksQuery";
import React from "react";

function wrapper() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return ({ children }: { children: React.ReactNode }) =>
    React.createElement(QueryClientProvider, { client: qc }, children);
}

describe("useTasksQuery", () => {
  it("fetches tasks for a project", async () => {
    server.use(
      http.get("*/tasks", () =>
        HttpResponse.json({
          data: [{ id: "t1", title: "Fix bug", status: "todo", priority: "high", project_id: "p1", created_by: "u1", created_at: "2024-01-01", updated_at: "2024-01-01" }],
          meta: { total: 1, limit: 50, offset: 0 },
        })
      )
    );
    const { result } = renderHook(() => useTasksQuery({ project_id: "p1" }), { wrapper: wrapper() });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.items).toHaveLength(1);
    expect(result.current.data?.items[0]?.title).toBe("Fix bug");
  });

  it("is disabled when no project_id", () => {
    const { result } = renderHook(() => useTasksQuery({ project_id: "" }), { wrapper: wrapper() });
    expect(result.current.fetchStatus).toBe("idle");
  });
});
