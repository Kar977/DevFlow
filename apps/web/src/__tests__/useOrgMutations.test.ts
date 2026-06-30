import { describe, it, expect, beforeEach } from "vitest";
import { renderHook, waitFor, act } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { http, HttpResponse } from "msw";
import React from "react";
import { server } from "./mocks/server";
import { useCreateOrganization } from "@/features/organizations/hooks/useOrgMutations";
import { useOrgStore } from "@/shared/store/orgStore";

function wrapper() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return ({ children }: { children: React.ReactNode }) =>
    React.createElement(QueryClientProvider, { client: qc }, children);
}

beforeEach(() => {
  localStorage.clear();
  useOrgStore.setState({ activeOrgId: null });
});

describe("useCreateOrganization", () => {
  it("creates an org and sets it as active", async () => {
    server.use(
      http.post("*/organizations", () =>
        HttpResponse.json(
          { id: "org-new", name: "New Org", slug: "new-org", description: null },
          { status: 201 }
        )
      )
    );

    const { result } = renderHook(() => useCreateOrganization(), {
      wrapper: wrapper(),
    });

    await act(async () => {
      result.current.mutate({ name: "New Org" });
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(useOrgStore.getState().activeOrgId).toBe("org-new");
  });
});
