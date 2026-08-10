import { describe, it, expect } from "vitest";
import {
  formatWeekLabel,
  formatDayLabel,
  formatHours,
  formatPercent,
} from "@/shared/charts";

describe("formatDayLabel / formatWeekLabel", () => {
  it("formats an ISO date as dd.mm", () => {
    expect(formatDayLabel("2026-08-03")).toBe("03.08");
    expect(formatWeekLabel("2026-01-06")).toBe("06.01");
  });

  it("pads single-digit day and month", () => {
    expect(formatDayLabel("2026-01-05")).toBe("05.01");
  });

  it("returns the raw input when it cannot be parsed", () => {
    expect(formatDayLabel("not-a-date")).toBe("not-a-date");
  });
});

describe("formatHours", () => {
  it("formats to one decimal place with a unit suffix", () => {
    expect(formatHours(4.5)).toBe("4.5 h");
    expect(formatHours(0)).toBe("0.0 h");
    expect(formatHours(12)).toBe("12.0 h");
  });
});

describe("formatPercent", () => {
  it("rounds and appends a percent sign", () => {
    expect(formatPercent(72.3)).toBe("72%");
    expect(formatPercent(0)).toBe("0%");
    expect(formatPercent(99.6)).toBe("100%");
  });
});
