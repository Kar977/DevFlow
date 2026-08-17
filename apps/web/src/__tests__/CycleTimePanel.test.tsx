import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import type { ReactElement } from "react";
import React from "react";
import { CycleTimePanel } from "@/features/projects/components/CycleTimePanel";
import type { CycleTime } from "@/shared/types";

vi.mock("recharts", async (importOriginal) => {
  const actual = await importOriginal<typeof import("recharts")>();
  return {
    ...actual,
    ResponsiveContainer: ({ children }: { children: ReactElement }) =>
      React.cloneElement(children, { width: 400, height: 200 }),
  };
});

describe("CycleTimePanel", () => {
  it("renders the loading state", () => {
    render(<CycleTimePanel isLoading />);
    expect(screen.getByText("Ładowanie...")).toBeInTheDocument();
  });

  it("renders the empty state when there is no data", () => {
    render(<CycleTimePanel />);
    expect(screen.getByText("Brak historii statusów do policzenia.")).toBeInTheDocument();
  });

  it("renders the empty state when both stages and stuck are empty", () => {
    const data: CycleTime = { project_id: "p1", stages: [], stuck: [] };
    render(<CycleTimePanel data={data} />);
    expect(screen.getByText("Brak historii statusów do policzenia.")).toBeInTheDocument();
  });

  it("renders a Polish label for each stage", () => {
    const data: CycleTime = {
      project_id: "p1",
      stages: [
        { status: "backlog", average_hours: 2, sample_size: 3 },
        { status: "in_progress", average_hours: 5.5, sample_size: 2 },
      ],
      stuck: [],
    };
    render(<CycleTimePanel data={data} />);
    expect(screen.getByText("Backlog")).toBeInTheDocument();
    expect(screen.getByText("W toku")).toBeInTheDocument();
  });

  it("renders the stuck task list with title, status and hours", () => {
    const data: CycleTime = {
      project_id: "p1",
      stages: [],
      stuck: [
        { task_id: "t1", title: "Fix flaky test", status: "review", hours_in_status: 30 },
      ],
    };
    render(<CycleTimePanel data={data} />);
    expect(screen.getByText("Fix flaky test")).toBeInTheDocument();
    expect(screen.getByText("Review")).toBeInTheDocument();
    expect(screen.getByText("30.0 h")).toBeInTheDocument();
  });

  it("does not render the stuck section when there are no stuck tasks", () => {
    const data: CycleTime = {
      project_id: "p1",
      stages: [{ status: "done", average_hours: 1, sample_size: 1 }],
      stuck: [],
    };
    render(<CycleTimePanel data={data} />);
    expect(screen.queryByText("Najdłużej bez zmiany")).not.toBeInTheDocument();
  });
});
