import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import type { ReactElement } from "react";
import React from "react";
import { MetricTrendsPanel } from "@/features/metrics/components/MetricTrendsPanel";
import type { MetricTrends } from "@/shared/types";

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

const TRENDS: MetricTrends = {
  period_from: "2026-02-16T00:00:00Z",
  period_to: "2026-08-10T00:00:00Z",
  weeks: 4,
  series: [
    {
      metric_key: "tasks_completed",
      points: [
        { week_start: "2026-07-20", value: 1 },
        { week_start: "2026-07-27", value: 2 },
        { week_start: "2026-08-03", value: 0 },
        { week_start: "2026-08-10", value: 3 },
      ],
    },
    {
      metric_key: "active_hours",
      points: [
        { week_start: "2026-07-20", value: 5 },
        { week_start: "2026-07-27", value: 8 },
        { week_start: "2026-08-03", value: 0 },
        { week_start: "2026-08-10", value: 4 },
      ],
    },
    {
      metric_key: "completion_rate",
      points: [
        { week_start: "2026-07-20", value: null },
        { week_start: "2026-07-27", value: null },
        { week_start: "2026-08-03", value: null },
        { week_start: "2026-08-10", value: null },
      ],
    },
    {
      metric_key: "estimation_ratio",
      points: [
        { week_start: "2026-07-20", value: null },
        { week_start: "2026-07-27", value: null },
        { week_start: "2026-08-03", value: null },
        { week_start: "2026-08-10", value: null },
      ],
    },
  ],
};

describe("MetricTrendsPanel", () => {
  it("renders the loading state", () => {
    render(<MetricTrendsPanel isLoading weeks={26} onWeeksChange={() => {}} />);
    expect(screen.getByText("Ładowanie...")).toBeInTheDocument();
  });

  it("renders the empty state when there is no data", () => {
    render(<MetricTrendsPanel weeks={26} onWeeksChange={() => {}} />);
    expect(screen.getByText("Brak danych.")).toBeInTheDocument();
  });

  it("renders the chart for the default metric when it has values", () => {
    render(<MetricTrendsPanel data={TRENDS} weeks={26} onWeeksChange={() => {}} />);
    expect(screen.getByText("Długoterminowy trend metryki")).toBeInTheDocument();
    expect(screen.queryByText("Brak danych.")).not.toBeInTheDocument();
  });

  it("shows the empty state when the selected metric has no sampled values", () => {
    // completion_rate and estimation_ratio are all-null in the fixture —
    // the selector itself must still be interactive in that state.
    render(<MetricTrendsPanel data={TRENDS} weeks={26} onWeeksChange={() => {}} />);
    // Default metric (tasks_completed) has data, so no empty state yet.
    expect(screen.queryByText("Brak danych.")).not.toBeInTheDocument();
    // The metric selector trigger is present and shows the default label.
    expect(screen.getByText("Ukończone zadania")).toBeInTheDocument();
  });

  it("keeps the weeks selector visible in the empty state", () => {
    render(<MetricTrendsPanel weeks={12} onWeeksChange={() => {}} />);
    expect(screen.getByText("12 tyg.")).toBeInTheDocument();
    expect(screen.getByText("Brak danych.")).toBeInTheDocument();
  });
});
