import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { http, HttpResponse } from "msw";
import { server } from "./mocks/server";
import { CreateTaskModal } from "@/features/tasks/components/CreateTaskModal";
import { fromDueDateIso } from "@/features/tasks/lib/dueDate";
import { useOrgStore } from "@/shared/store/orgStore";

beforeEach(() => {
  useOrgStore.setState({ activeOrgId: null });
});

function renderModal(onClose = vi.fn()) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return {
    onClose,
    ...render(
      <QueryClientProvider client={qc}>
        <CreateTaskModal open onClose={onClose} projectId="p1" />
      </QueryClientProvider>
    ),
  };
}

describe("CreateTaskModal", () => {
  it("submits the form and creates a task with the given project_id", async () => {
    let capturedBody: unknown;
    server.use(
      http.post("*/tasks", async ({ request }) => {
        capturedBody = await request.json();
        return HttpResponse.json(
          {
            id: "t1",
            title: "Fix bug",
            status: "todo",
            priority: "medium",
            project_id: "p1",
            created_by: "u1",
            created_at: "2024-01-01",
            updated_at: "2024-01-01",
          },
          { status: 201 }
        );
      })
    );

    const { onClose } = renderModal();

    await userEvent.type(screen.getByLabelText(/tytuł/i), "Fix bug");
    await userEvent.click(screen.getByRole("button", { name: /utwórz/i }));

    await waitFor(() => expect(onClose).toHaveBeenCalled());
    expect(capturedBody).toMatchObject({ title: "Fix bug", project_id: "p1", priority: "medium" });
  });

  it("shows a validation error when title is empty", async () => {
    renderModal();

    await userEvent.click(screen.getByRole("button", { name: /utwórz/i }));

    await waitFor(() =>
      expect(screen.getByText(/tytuł jest wymagany/i)).toBeInTheDocument()
    );
  });

  it("includes the selected assignee_id in the create payload", async () => {
    useOrgStore.setState({ activeOrgId: "org-1" });
    let capturedBody: unknown;
    server.use(
      http.get("*/organizations/org-1/members", () =>
        HttpResponse.json({
          data: [
            {
              id: "mem-1",
              org_id: "org-1",
              user_id: "user-42",
              role: "member",
              joined_at: "2024-01-01T00:00:00Z",
              display_name: "Jan Kowalski",
            },
          ],
        })
      ),
      http.post("*/tasks", async ({ request }) => {
        capturedBody = await request.json();
        return HttpResponse.json(
          {
            id: "t1",
            title: "Fix bug",
            status: "todo",
            priority: "medium",
            project_id: "p1",
            assignee_id: "user-42",
            created_by: "u1",
            created_at: "2024-01-01",
            updated_at: "2024-01-01",
          },
          { status: 201 }
        );
      })
    );

    const { onClose } = renderModal();

    await userEvent.type(screen.getByLabelText(/tytuł/i), "Fix bug");
    await userEvent.click(screen.getByRole("combobox", { name: "Przypisano do" }));
    const option = await screen.findByRole("option", { name: "Jan Kowalski" });
    await userEvent.click(option);
    await userEvent.click(screen.getByRole("button", { name: /utwórz/i }));

    await waitFor(() => expect(onClose).toHaveBeenCalled());
    expect(capturedBody).toMatchObject({ assignee_id: "user-42" });
  });

  it("includes a due_date in the create payload when a date is picked", async () => {
    let capturedBody: { due_date?: string } = {};
    server.use(
      http.post("*/tasks", async ({ request }) => {
        capturedBody = (await request.json()) as { due_date?: string };
        return HttpResponse.json(
          {
            id: "t1",
            title: "Fix bug",
            status: "todo",
            priority: "medium",
            project_id: "p1",
            created_by: "u1",
            created_at: "2024-01-01",
            updated_at: "2024-01-01",
          },
          { status: 201 }
        );
      })
    );

    const { onClose } = renderModal();

    await userEvent.type(screen.getByLabelText(/tytuł/i), "Fix bug");
    fireEvent.change(screen.getByLabelText(/termin/i), {
      target: { value: "2026-08-20" },
    });
    await userEvent.click(screen.getByRole("button", { name: /utwórz/i }));

    await waitFor(() => expect(onClose).toHaveBeenCalled());
    expect(capturedBody.due_date).toBeTruthy();
    expect(fromDueDateIso(capturedBody.due_date as string)).toBe("2026-08-20");
  });
});
