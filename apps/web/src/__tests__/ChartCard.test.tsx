import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { ChartCard } from "@/shared/charts";

describe("ChartCard", () => {
  it("renders the loading state", () => {
    render(
      <ChartCard title="Velocity" isLoading>
        <div>chart</div>
      </ChartCard>
    );
    expect(screen.getByText("Ładowanie...")).toBeInTheDocument();
    expect(screen.queryByText("chart")).not.toBeInTheDocument();
  });

  it("renders the empty state with the default label", () => {
    render(
      <ChartCard title="Velocity" isEmpty>
        <div>chart</div>
      </ChartCard>
    );
    expect(screen.getByText("Brak danych.")).toBeInTheDocument();
  });

  it("renders a custom empty label", () => {
    render(
      <ChartCard title="Velocity" isEmpty emptyLabel="Brak PR-ów w tym okresie.">
        <div>chart</div>
      </ChartCard>
    );
    expect(screen.getByText("Brak PR-ów w tym okresie.")).toBeInTheDocument();
  });

  it("renders title, subtitle, and children when data is present", () => {
    render(
      <ChartCard title="Velocity" subtitle="ostatnie 12 tygodni">
        <div>chart-content</div>
      </ChartCard>
    );
    expect(screen.getByText("Velocity")).toBeInTheDocument();
    expect(screen.getByText("ostatnie 12 tygodni")).toBeInTheDocument();
    expect(screen.getByText("chart-content")).toBeInTheDocument();
  });

  it("omits the legend for a single series", () => {
    render(
      <ChartCard title="Velocity" series={[{ label: "Zadania", color: "#2a78d6" }]}>
        <div>chart</div>
      </ChartCard>
    );
    expect(screen.queryByText("Zadania")).not.toBeInTheDocument();
  });

  it("renders a legend chip per series when there are 2 or more", () => {
    render(
      <ChartCard
        title="Przepływ PR"
        series={[
          { label: "Otwarte", color: "#2a78d6" },
          { label: "Zmergowane", color: "#eb6834" },
        ]}
      >
        <div>chart</div>
      </ChartCard>
    );
    expect(screen.getByText("Otwarte")).toBeInTheDocument();
    expect(screen.getByText("Zmergowane")).toBeInTheDocument();
  });
});
