import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { KpiCard } from "@/features/dashboard/components/KpiCard";

describe("KpiCard", () => {
  it("shows value and positive delta", () => {
    render(<KpiCard title="Tasks done" value={42} delta={15.5} />);
    expect(screen.getByText("42")).toBeInTheDocument();
    expect(screen.getByText("+15.5%")).toBeInTheDocument();
  });

  it("shows negative delta in red", () => {
    render(<KpiCard title="Hours" value={12} delta={-8.0} />);
    const delta = screen.getByText("-8.0%");
    expect(delta).toBeInTheDocument();
    expect(delta).toHaveClass("text-red-500");
  });

  it("shows zero delta as positive", () => {
    render(<KpiCard title="Rate" value={100} delta={0} />);
    expect(screen.getByText("+0.0%")).toBeInTheDocument();
  });
});
