import { describe, it, expect, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { http, HttpResponse } from "msw";
import React from "react";
import { server } from "./mocks/server";
import { OrgSwitcher } from "@/features/organizations/components/OrgSwitcher";
import { useOrgStore } from "@/shared/store/orgStore";

function wrapper(children: React.ReactNode) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return React.createElement(QueryClientProvider, { client: qc }, children);
}

beforeEach(() => {
  localStorage.clear();
  useOrgStore.setState({ activeOrgId: null });
});

describe("OrgSwitcher", () => {
  it("auto-selects the first org when activeOrgId is null", async () => {
    server.use(
      http.get("*/organizations", () =>
        HttpResponse.json({
          data: [{ id: "org-1", name: "My Workspace", slug: "my-workspace" }],
        })
      )
    );

    render(wrapper(React.createElement(OrgSwitcher)));

    await waitFor(() =>
      expect(useOrgStore.getState().activeOrgId).toBe("org-1")
    );
  });

  it("shows org name in the switcher after auto-select", async () => {
    server.use(
      http.get("*/organizations", () =>
        HttpResponse.json({
          data: [{ id: "org-2", name: "Team Alpha", slug: "team-alpha" }],
        })
      )
    );

    render(wrapper(React.createElement(OrgSwitcher)));

    await waitFor(() =>
      expect(screen.getByText("Team Alpha")).toBeTruthy()
    );
  });

  it('shows "Brak organizacji" and "+" button when no orgs returned', async () => {
    server.use(
      http.get("*/organizations", () => HttpResponse.json({ data: [] }))
    );

    render(wrapper(React.createElement(OrgSwitcher)));

    await waitFor(() =>
      expect(screen.getByText("Brak organizacji")).toBeTruthy()
    );
    expect(screen.getByRole("button", { name: /utwórz organizację/i })).toBeTruthy();
  });
});
