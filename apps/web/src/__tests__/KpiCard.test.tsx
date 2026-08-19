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

  it("renders no delta indicator when delta is omitted", () => {
    render(<KpiCard title="Stale PRs" value={3} />);
    expect(screen.getByText("3")).toBeInTheDocument();
    expect(screen.queryByText(/%/)).not.toBeInTheDocument();
  });

  it("renders null value as an em dash, never 0", () => {
    render(<KpiCard title="Czas do 1. review (h)" value={null} />);
    expect(screen.getByText("—")).toBeInTheDocument();
    expect(screen.queryByText("0")).not.toBeInTheDocument();
  });

  it("formats the value with formatValue when provided", () => {
    render(
      <KpiCard title="Czas do 1. review (h)" value={4.5} formatValue={(v) => `${v} h`} />
    );
    expect(screen.getByText("4.5 h")).toBeInTheDocument();
  });

  it("inverts delta color for lower-is-better metrics", () => {
    // A positive delta (wait time went up) must read as a regression (red)
    // when invertDelta is set — the opposite of the default polarity.
    render(<KpiCard title="Czas do 1. review (h)" value={10} delta={20} invertDelta />);
    const delta = screen.getByText("+20.0%");
    expect(delta).toHaveClass("text-red-500");
  });

  it("keeps a negative delta green under invertDelta (wait time went down)", () => {
    render(<KpiCard title="Czas do 1. review (h)" value={10} delta={-15} invertDelta />);
    const delta = screen.getByText("-15.0%");
    expect(delta).toHaveClass("text-green-500");
  });

  it("shows the hint as a native title attribute for a tooltip", () => {
    render(<KpiCard title="Stale PRs" value={3} hint="Otwarte PR-y bez aktywności" />);
    expect(screen.getByText("3").closest("[title]")).toHaveAttribute(
      "title",
      "Otwarte PR-y bez aktywności"
    );
  });
});
