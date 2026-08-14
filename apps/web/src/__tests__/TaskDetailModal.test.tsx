import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { http, HttpResponse } from "msw";
import { server } from "./mocks/server";
import { TaskDetailModal } from "@/features/tasks/components/TaskDetailModal";
import { fromDueDateIso } from "@/features/tasks/lib/dueDate";
import { useOrgStore } from "@/shared/store/orgStore";
import type { Task } from "@/features/tasks/hooks/useTasksQuery";

const baseTask: Task = {
  id: "task-1",
  title: "Fix bug",
  description: "",
  status: "todo",
  priority: "medium",
  project_id: "p1",
  assignee_id: "user-42",
  created_by: "user-42",
  created_at: "2024-03-15T00:00:00Z",
  updated_at: "2024-03-15T00:00:00Z",
};

const members = [
  {
    id: "mem-1",
    org_id: "org-1",
    user_id: "user-42",
    role: "member",
    joined_at: "2024-01-01T00:00:00Z",
    display_name: "Jan Kowalski",
  },
];

function renderModal(task: Task, onClose = vi.fn()) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return {
    onClose,
    ...render(
      <QueryClientProvider client={qc}>
        <TaskDetailModal task={task} open onClose={onClose} />
      </QueryClientProvider>
    ),
  };
}

beforeEach(() => {
  useOrgStore.setState({ activeOrgId: "org-1" });
  server.use(
    http.get("*/organizations/org-1/members", () =>
      HttpResponse.json({ data: members })
    )
  );
});

describe("TaskDetailModal", () => {
  it("shows who created the task and when", async () => {
    renderModal(baseTask);

    await waitFor(() =>
      expect(screen.getByText(/utworzono przez jan kowalski/i)).toBeInTheDocument()
    );
  });

  it("sends assignee_id: null when the user picks Nieprzypisane", async () => {
    let capturedBody: unknown;
    server.use(
      http.patch("*/tasks/task-1", async ({ request }) => {
        capturedBody = await request.json();
        return HttpResponse.json({ ...baseTask, assignee_id: null });
      })
    );

    const { onClose } = renderModal(baseTask);

    await waitFor(() =>
      expect(screen.getByRole("combobox", { name: "Przypisano do" })).toBeInTheDocument()
    );
    await userEvent.click(screen.getByRole("combobox", { name: "Przypisano do" }));
    const option = await screen.findByRole("option", { name: "Nieprzypisane" });
    await userEvent.click(option);
    await userEvent.click(screen.getByRole("button", { name: /zapisz/i }));

    await waitFor(() => expect(onClose).toHaveBeenCalled());
    expect(capturedBody).toMatchObject({ assignee_id: null });
  });

  it("prefills the due date input from the task and sends null when cleared", async () => {
    let capturedBody: { due_date?: string | null } = {};
    server.use(
      http.patch("*/tasks/task-1", async ({ request }) => {
        capturedBody = (await request.json()) as { due_date?: string | null };
        return HttpResponse.json({ ...baseTask, due_date: null });
      })
    );
    const dueTask: Task = { ...baseTask, due_date: "2026-08-20T21:59:59.000Z" };

    renderModal(dueTask, vi.fn());

    const dueInput = screen.getByLabelText(/termin/i) as HTMLInputElement;
    expect(dueInput.value).toBe(fromDueDateIso(dueTask.due_date as string));

    fireEvent.change(dueInput, { target: { value: "" } });
    await userEvent.click(screen.getByRole("button", { name: /zapisz/i }));

    await waitFor(() => expect(capturedBody.due_date).toBeNull());
  });
});
