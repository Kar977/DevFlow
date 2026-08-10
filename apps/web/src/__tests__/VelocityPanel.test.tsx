import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import type { ReactElement } from "react";
import React from "react";
import { VelocityPanel } from "@/features/metrics/components/VelocityPanel";
import type { Velocity } from "@/shared/types";

// ResponsiveContainer measures 0x0 in jsdom and renders nothing; clone the
// chart child with explicit dimensions so the chart actually mounts.
vi.mock("recharts", async (importOriginal) => {
  const actual = await importOriginal<typeof import("recharts")>();
  return {
    ...actual,
    ResponsiveContainer: ({ children }: { children: ReactElement }) =>
      React.cloneElement(children, { width: 400, height: 200 }),
  };
});

const VELOCITY: Velocity = {
  period_from: "2026-07-11T00:00:00Z",
  period_to: "2026-08-10T00:00:00Z",
  total_done: 5,
  weeks: 4.29,
  average_per_week: 1.17,
  trend_pct: 10.0,
  weekly: [
    { week_start: "2026-07-13", tasks_completed: 0 },
    { week_start: "2026-07-20", tasks_completed: 2 },
    { week_start: "2026-07-27", tasks_completed: 3 },
  ],
};

describe("VelocityPanel", () => {
  it("renders the loading state", () => {
    render(<VelocityPanel isLoading />);
    expect(screen.getByText("Ładowanie...")).toBeInTheDocument();
  });

  it("renders the empty state when there is no data", () => {
    render(<VelocityPanel />);
    expect(screen.getByText("Brak danych.")).toBeInTheDocument();
  });

  it("renders the title and chart when weekly data is present", () => {
    // Regression guard: this reads `data.weekly` (the real backend field),
    // not `data.weeks` as an array — that mismatch was the bug that made
    // this chart never render in production.
    render(<VelocityPanel data={VELOCITY} />);
    expect(screen.getByText("Velocity (zadania/tydzień)")).toBeInTheDocument();
    expect(screen.queryByText("Brak danych.")).not.toBeInTheDocument();
  });
});
