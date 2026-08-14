import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { TaskFilters } from "@/features/tasks/components/TaskFilters";

const members = [
  { user_id: "user-1", display_name: "Jan Kowalski" },
  { user_id: "user-2", display_name: "Anna Nowak" },
];

describe("TaskFilters", () => {
  it("calls onAssigneeChange with the selected member's user_id", async () => {
    const onAssigneeChange = vi.fn();
    render(
      <TaskFilters
        status="all"
        onStatusChange={vi.fn()}
        assigneeId=""
        onAssigneeChange={onAssigneeChange}
        members={members}
        overdueOnly={false}
        onOverdueOnlyChange={vi.fn()}
      />
    );

    await userEvent.click(screen.getByRole("combobox", { name: /filtruj wg osoby/i }));
    const option = await screen.findByRole("option", { name: "Anna Nowak" });
    await userEvent.click(option);

    expect(onAssigneeChange).toHaveBeenCalledWith("user-2");
  });

  it("calls onAssigneeChange with an empty string when Wszyscy is selected", async () => {
    const onAssigneeChange = vi.fn();
    render(
      <TaskFilters
        status="all"
        onStatusChange={vi.fn()}
        assigneeId="user-1"
        onAssigneeChange={onAssigneeChange}
        members={members}
        overdueOnly={false}
        onOverdueOnlyChange={vi.fn()}
      />
    );

    await userEvent.click(screen.getByRole("combobox", { name: /filtruj wg osoby/i }));
    const option = await screen.findByRole("option", { name: "Wszyscy" });
    await userEvent.click(option);

    expect(onAssigneeChange).toHaveBeenCalledWith("");
  });

  it("calls onOverdueOnlyChange when the checkbox is toggled", async () => {
    const onOverdueOnlyChange = vi.fn();
    render(
      <TaskFilters
        status="all"
        onStatusChange={vi.fn()}
        assigneeId=""
        onAssigneeChange={vi.fn()}
        members={members}
        overdueOnly={false}
        onOverdueOnlyChange={onOverdueOnlyChange}
      />
    );

    await userEvent.click(screen.getByLabelText("Tylko przeterminowane"));

    expect(onOverdueOnlyChange).toHaveBeenCalledWith(true);
  });
});
