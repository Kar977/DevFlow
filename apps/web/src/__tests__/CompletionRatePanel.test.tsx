import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import type { ReactElement } from "react";
import React from "react";
import { CompletionRatePanel } from "@/features/metrics/components/CompletionRatePanel";
import type { CompletionRate } from "@/shared/types";

vi.mock("recharts", async (importOriginal) => {
  const actual = await importOriginal<typeof import("recharts")>();
  return {
    ...actual,
    ResponsiveContainer: ({ children }: { children: ReactElement }) =>
      React.cloneElement(children, { width: 400, height: 100 }),
  };
});

describe("CompletionRatePanel", () => {
  it("renders the loading state", () => {
    render(<CompletionRatePanel isLoading />);
    expect(screen.getByText("Ładowanie...")).toBeInTheDocument();
  });

  it("renders the empty state when there is no data", () => {
    render(<CompletionRatePanel />);
    expect(screen.getByText("Brak danych.")).toBeInTheDocument();
  });

  it("renders the real backend field names without the *100 bug", () => {
    // Regression guard: `completion_rate` is already 0-100 server-side
    // (metrics.py: `rate = done / total * 100`). Multiplying by 100 again
    // in the panel produced "7230%" — this asserts the display value
    // matches the raw field, not a re-scaled one.
    const data: CompletionRate = {
      period_from: "2026-07-11T00:00:00Z",
      period_to: "2026-08-10T00:00:00Z",
      done: 47,
      cancelled: 5,
      open: 13,
      completion_rate: 72.3,
    };
    render(<CompletionRatePanel data={data} />);
    expect(screen.getByText("72%")).toBeInTheDocument();
    expect(screen.queryByText(/7230/)).not.toBeInTheDocument();
  });

  it("renders a legend chip for each of the three segments", () => {
    const data: CompletionRate = {
      period_from: "2026-07-11T00:00:00Z",
      period_to: "2026-08-10T00:00:00Z",
      done: 10,
      cancelled: 1,
      open: 2,
      completion_rate: 76.9,
    };
    render(<CompletionRatePanel data={data} />);
    expect(screen.getByText("Ukończone")).toBeInTheDocument();
    expect(screen.getByText("Otwarte")).toBeInTheDocument();
    expect(screen.getByText("Anulowane")).toBeInTheDocument();
  });
});
