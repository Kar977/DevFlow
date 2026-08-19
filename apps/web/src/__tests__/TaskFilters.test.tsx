import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { TaskFilters } from "@/features/tasks/components/TaskFilters";
import { useOrgStore } from "@/shared/store/orgStore";

const members = [
  { user_id: "user-1", display_name: "Jan Kowalski" },
  { user_id: "user-2", display_name: "Anna Nowak" },
];

function renderFilters(props: Partial<React.ComponentProps<typeof TaskFilters>> = {}) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <TaskFilters
        status="all"
        onStatusChange={vi.fn()}
        assigneeId=""
        onAssigneeChange={vi.fn()}
        members={members}
        overdueOnly={false}
        onOverdueOnlyChange={vi.fn()}
        sprintFilter=""
        onSprintFilterChange={vi.fn()}
        {...props}
      />
    </QueryClientProvider>
  );
}

beforeEach(() => {
  // TaskFilters queries the sprint series itself (for the sprint filter
  // select) — no org, no query, keeping these tests focused on the props
  // under test rather than sprint fixtures.
  useOrgStore.setState({ activeOrgId: null });
});

describe("TaskFilters", () => {
  it("calls onAssigneeChange with the selected member's user_id", async () => {
    const onAssigneeChange = vi.fn();
    renderFilters({ onAssigneeChange });

    await userEvent.click(screen.getByRole("combobox", { name: /filtruj wg osoby/i }));
    const option = await screen.findByRole("option", { name: "Anna Nowak" });
    await userEvent.click(option);

    expect(onAssigneeChange).toHaveBeenCalledWith("user-2");
  });

  it("calls onAssigneeChange with an empty string when Wszyscy is selected", async () => {
    const onAssigneeChange = vi.fn();
    renderFilters({ assigneeId: "user-1", onAssigneeChange });

    await userEvent.click(screen.getByRole("combobox", { name: /filtruj wg osoby/i }));
    const option = await screen.findByRole("option", { name: "Wszyscy" });
    await userEvent.click(option);

    expect(onAssigneeChange).toHaveBeenCalledWith("");
  });

  it("calls onOverdueOnlyChange when the checkbox is toggled", async () => {
    const onOverdueOnlyChange = vi.fn();
    renderFilters({ onOverdueOnlyChange });

    await userEvent.click(screen.getByLabelText("Tylko przeterminowane"));

    expect(onOverdueOnlyChange).toHaveBeenCalledWith(true);
  });

  it("calls onSprintFilterChange with 'backlog' when Backlog is selected", async () => {
    const onSprintFilterChange = vi.fn();
    renderFilters({ onSprintFilterChange });

    await userEvent.click(screen.getByRole("combobox", { name: /filtruj wg sprintu/i }));
    const option = await screen.findByRole("option", { name: "Backlog" });
    await userEvent.click(option);

    expect(onSprintFilterChange).toHaveBeenCalledWith("backlog");
  });

  it("calls onSprintFilterChange with an empty string when Wszystkie sprinty is selected", async () => {
    const onSprintFilterChange = vi.fn();
    renderFilters({ sprintFilter: "backlog", onSprintFilterChange });

    await userEvent.click(screen.getByRole("combobox", { name: /filtruj wg sprintu/i }));
    const option = await screen.findByRole("option", { name: "Wszystkie sprinty" });
    await userEvent.click(option);

    expect(onSprintFilterChange).toHaveBeenCalledWith("");
  });
});
