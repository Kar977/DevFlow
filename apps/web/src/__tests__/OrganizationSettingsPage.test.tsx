import { describe, it, expect, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { http, HttpResponse } from "msw";
import { server } from "./mocks/server";
import { OrganizationSettingsPage } from "@/features/organizations/pages/OrganizationSettingsPage";
import { useOrgStore } from "@/shared/store/orgStore";
import { useAuthStore } from "@/shared/store/authStore";

const ORG_ID = "11111111-1111-1111-1111-111111111111";
const OWNER_ID = "22222222-2222-2222-2222-222222222222";
const MEMBER_ID = "33333333-3333-3333-3333-333333333333";

const org = {
  id: ORG_ID,
  name: "Acme",
  slug: "acme",
  description: "A company",
  created_by: OWNER_ID,
  created_at: "2024-01-01T00:00:00Z",
  updated_at: "2024-01-01T00:00:00Z",
};

function membersFixture() {
  return [
    {
      id: "mem-owner",
      org_id: ORG_ID,
      user_id: OWNER_ID,
      role: "owner",
      joined_at: "2024-01-01T00:00:00Z",
      display_name: "Jan Kowalski",
    },
    {
      id: "mem-member",
      org_id: ORG_ID,
      user_id: MEMBER_ID,
      role: "member",
      joined_at: "2024-01-02T00:00:00Z",
      display_name: "Anna Nowak",
    },
  ];
}

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <OrganizationSettingsPage />
    </QueryClientProvider>
  );
}

function setAsOwner() {
  useAuthStore.setState({
    user: {
      id: OWNER_ID,
      email: "owner@example.com",
      full_name: "Jan Kowalski",
      avatar_url: null,
      created_at: "2024-01-01T00:00:00Z",
      updated_at: "2024-01-01T00:00:00Z",
    },
  });
}

function setAsMember() {
  useAuthStore.setState({
    user: {
      id: MEMBER_ID,
      email: "member@example.com",
      full_name: "Anna Nowak",
      avatar_url: null,
      created_at: "2024-01-01T00:00:00Z",
      updated_at: "2024-01-01T00:00:00Z",
    },
  });
}

beforeEach(() => {
  useOrgStore.setState({ activeOrgId: ORG_ID });
  server.use(
    http.get(`*/organizations/${ORG_ID}`, () => HttpResponse.json(org)),
    http.get(`*/organizations/${ORG_ID}/members`, () =>
      HttpResponse.json({ data: membersFixture() })
    )
  );
});

describe("OrganizationSettingsPage", () => {
  it("renders the three settings tabs", async () => {
    setAsOwner();
    renderPage();
    await waitFor(() =>
      expect(screen.getByRole("tab", { name: "Ogólne" })).toBeInTheDocument()
    );
    expect(screen.getByRole("tab", { name: "Członkowie" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "GitHub" })).toBeInTheDocument();
  });

  it("saves name and description from the Ogólne tab", async () => {
    setAsOwner();
    let capturedBody: unknown;
    server.use(
      http.patch(`*/organizations/${ORG_ID}`, async ({ request }) => {
        capturedBody = await request.json();
        return HttpResponse.json({ ...org, name: "Acme Updated" });
      })
    );
    renderPage();

    const nameInput = await screen.findByLabelText("Nazwa");
    expect((nameInput as HTMLInputElement).value).toBe("Acme");
    await userEvent.clear(nameInput);
    await userEvent.type(nameInput, "Acme Updated");
    await userEvent.click(screen.getByRole("button", { name: /zapisz/i }));

    await waitFor(() =>
      expect(capturedBody).toMatchObject({ name: "Acme Updated", description: "A company" })
    );
  });

  it("shows member display names instead of raw user ids", async () => {
    setAsOwner();
    renderPage();
    await userEvent.click(await screen.findByRole("tab", { name: "Członkowie" }));

    await waitFor(() => expect(screen.getByText("Anna Nowak")).toBeInTheDocument());
    expect(screen.queryByText(MEMBER_ID)).not.toBeInTheDocument();
  });

  it("PATCHes the member role via the role select", async () => {
    setAsOwner();
    let capturedBody: unknown;
    let capturedUrl = "";
    server.use(
      http.patch(`*/organizations/${ORG_ID}/members/${MEMBER_ID}`, async ({ request }) => {
        capturedUrl = request.url;
        capturedBody = await request.json();
        return HttpResponse.json({
          id: "mem-member",
          org_id: ORG_ID,
          user_id: MEMBER_ID,
          role: "admin",
          joined_at: "2024-01-02T00:00:00Z",
          display_name: "Anna Nowak",
        });
      })
    );
    renderPage();
    await userEvent.click(await screen.findByRole("tab", { name: "Członkowie" }));
    await waitFor(() => expect(screen.getByText("Anna Nowak")).toBeInTheDocument());

    await userEvent.click(screen.getByRole("combobox", { name: "Rola: Anna Nowak" }));
    const option = await screen.findByRole("option", { name: "Admin" });
    await userEvent.click(option);

    await waitFor(() => expect(capturedBody).toEqual({ role: "admin" }));
    expect(capturedUrl).toContain(`/organizations/${ORG_ID}/members/${MEMBER_ID}`);
  });

  it("only offers the owner role option to an owner", async () => {
    setAsOwner();
    renderPage();
    await userEvent.click(await screen.findByRole("tab", { name: "Członkowie" }));
    await waitFor(() => expect(screen.getByText("Anna Nowak")).toBeInTheDocument());

    await userEvent.click(screen.getByRole("combobox", { name: "Rola: Anna Nowak" }));
    expect(await screen.findByRole("option", { name: "Owner" })).toBeInTheDocument();
  });

  it("disables the role select for a plain member viewer", async () => {
    setAsMember();
    renderPage();
    await userEvent.click(await screen.findByRole("tab", { name: "Członkowie" }));
    await waitFor(() => expect(screen.getByText("Anna Nowak")).toBeInTheDocument());

    expect(screen.getByRole("combobox", { name: "Rola: Anna Nowak" })).toBeDisabled();
  });
});
