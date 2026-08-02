import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import React from "react";
import { ReportsList } from "@/features/reports/components/ReportsList";
import type { Report } from "@/features/reports/hooks/useReportsQuery";

function wrapper(children: React.ReactNode) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return React.createElement(QueryClientProvider, { client: qc }, children);
}

function makeReport(overrides: Partial<Report> = {}): Report {
  return {
    id: "r1",
    type: "weekly_summary",
    format: "json",
    status: "ready",
    created_at: "2026-01-01T00:00:00Z",
    user_id: "u1",
    ...overrides,
  };
}

describe("ReportsList", () => {
  it("shows CSV and PDF export buttons for a ready report", () => {
    render(wrapper(<ReportsList reports={[makeReport({ status: "ready" })]} />));
    expect(screen.getByRole("button", { name: "CSV" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "PDF" })).toBeInTheDocument();
  });

  it("hides export buttons for a pending report", () => {
    render(wrapper(<ReportsList reports={[makeReport({ status: "pending" })]} />));
    expect(screen.queryByRole("button", { name: "CSV" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "PDF" })).not.toBeInTheDocument();
  });

  it("shows empty state when there are no reports", () => {
    render(wrapper(<ReportsList reports={[]} />));
    expect(screen.getByText("Brak raportów.")).toBeInTheDocument();
  });
});
