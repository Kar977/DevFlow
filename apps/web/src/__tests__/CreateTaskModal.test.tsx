import { describe, it, expect, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { http, HttpResponse } from "msw";
import { server } from "./mocks/server";
import { CreateTaskModal } from "@/features/tasks/components/CreateTaskModal";

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
});
