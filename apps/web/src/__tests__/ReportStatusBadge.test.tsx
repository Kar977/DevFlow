import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { ReportStatusBadge } from "@/features/reports/components/ReportStatusBadge";

describe("ReportStatusBadge", () => {
  it("shows Oczekuje for pending", () => {
    render(<ReportStatusBadge status="pending" />);
    expect(screen.getByText("Oczekuje")).toBeInTheDocument();
  });

  it("shows pulsing badge for generating", () => {
    render(<ReportStatusBadge status="generating" />);
    const badge = screen.getByText("Generowanie...");
    expect(badge).toBeInTheDocument();
    expect(badge).toHaveClass("animate-pulse");
  });

  it("shows green badge for ready", () => {
    render(<ReportStatusBadge status="ready" />);
    const badge = screen.getByText("Gotowy");
    expect(badge).toBeInTheDocument();
    expect(badge).toHaveClass("text-green-700");
  });

  it("shows red badge for failed", () => {
    render(<ReportStatusBadge status="failed" />);
    const badge = screen.getByText("Błąd");
    expect(badge).toHaveClass("text-red-700");
  });
});
