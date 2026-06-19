import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { DateRangePicker } from "@/features/metrics/components/DateRangePicker";

describe("DateRangePicker", () => {
  it("renders date inputs and apply button", () => {
    render(<DateRangePicker onApply={vi.fn()} />);
    expect(screen.getByLabelText("Od")).toBeInTheDocument();
    expect(screen.getByLabelText("Do")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /zastosuj/i })).toBeInTheDocument();
  });

  it("apply button is disabled when dates not set", () => {
    render(<DateRangePicker onApply={vi.fn()} />);
    expect(screen.getByRole("button", { name: /zastosuj/i })).toBeDisabled();
  });

  it("calls onApply with selected dates", async () => {
    const onApply = vi.fn();
    render(<DateRangePicker onApply={onApply} />);
    fireEvent.change(screen.getByLabelText("Od"), { target: { value: "2026-06-01" } });
    fireEvent.change(screen.getByLabelText("Do"), { target: { value: "2026-06-30" } });
    await userEvent.click(screen.getByRole("button", { name: /zastosuj/i }));
    expect(onApply).toHaveBeenCalledWith({ date_from: "2026-06-01", date_to: "2026-06-30" });
  });
});
