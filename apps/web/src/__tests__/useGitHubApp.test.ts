import { describe, it, expect } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { http, HttpResponse } from "msw";
import { server } from "./mocks/server";
import {
  useInstallationsQuery,
  useSyncRunsQuery,
} from "@/features/github/hooks/useGitHubApp";
import React from "react";

const ORG_ID = "org-1";

function wrapper() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return ({ children }: { children: React.ReactNode }) =>
    React.createElement(QueryClientProvider, { client: qc }, children);
}

describe("useInstallationsQuery", () => {
  it("fetches installations for the active organization", async () => {
    server.use(
      http.get("*/integrations/github/app/installations", ({ request }) => {
        const orgId = new URL(request.url).searchParams.get("organization_id");
        expect(orgId).toBe(ORG_ID);
        return HttpResponse.json({
          items: [
            {
              id: "inst-uuid",
              installation_id: 42,
              account_login: "octo-org",
              account_type: "Organization",
              account_avatar_url: null,
              repository_selection: "selected",
              suspended_at: null,
              created_at: "2026-07-01T10:00:00Z",
            },
          ],
        });
      })
    );
    const { result } = renderHook(() => useInstallationsQuery(ORG_ID), {
      wrapper: wrapper(),
    });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.items[0]?.account_login).toBe("octo-org");
  });

  it("is disabled without an active organization", () => {
    const { result } = renderHook(() => useInstallationsQuery(null), {
      wrapper: wrapper(),
    });
    expect(result.current.fetchStatus).toBe("idle");
  });
});

describe("useSyncRunsQuery", () => {
  it("fetches sync runs", async () => {
    server.use(
      http.get("*/integrations/github/sync-runs", () =>
        HttpResponse.json({
          items: [
            {
              id: "run-1",
              status: "completed",
              repos_synced: 2,
              prs_synced: 10,
              reviews_synced: 4,
              error_message: null,
              started_at: "2026-07-04T10:00:00Z",
              finished_at: "2026-07-04T10:01:00Z",
            },
          ],
        })
      )
    );
    const { result } = renderHook(() => useSyncRunsQuery(ORG_ID), {
      wrapper: wrapper(),
    });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.items[0]?.status).toBe("completed");
  });
});
