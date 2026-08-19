import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemberFilter } from "@/features/dashboard/components/MemberFilter";

const items = [
  { user_id: "u1", display_name: "Jan Kowalski" },
  { user_id: "u2", display_name: "Anna Nowak", disabled: true, hint: "brak konta GitHub" },
];

describe("MemberFilter", () => {
  it("always offers a 'whole team' option first", () => {
    render(<MemberFilter value="" onChange={vi.fn()} items={items} />);
    const options = screen.getAllByRole("option") as HTMLOptionElement[];
    expect(options[0]).toHaveTextContent("Cały zespół");
    expect(options[0].value).toBe("");
  });

  it("lists every member by display name", () => {
    render(<MemberFilter value="" onChange={vi.fn()} items={items} />);
    expect(screen.getByRole("option", { name: "Jan Kowalski" })).toBeInTheDocument();
  });

  it("appends the hint and disables members without a linked GitHub account", () => {
    render(<MemberFilter value="" onChange={vi.fn()} items={items} />);
    const option = screen.getByRole("option", {
      name: "Anna Nowak (brak konta GitHub)",
    }) as HTMLOptionElement;
    expect(option.disabled).toBe(true);
  });

  it("calls onChange with the selected member's user_id", async () => {
    const onChange = vi.fn();
    render(<MemberFilter value="" onChange={onChange} items={items} />);
    await userEvent.selectOptions(screen.getByLabelText("Członek:"), "u1");
    expect(onChange).toHaveBeenCalledWith("u1");
  });

  it("renders without members without crashing (still loading)", () => {
    render(<MemberFilter value="" onChange={vi.fn()} items={undefined} />);
    expect(screen.getByRole("option", { name: "Cały zespół" })).toBeInTheDocument();
  });
});
