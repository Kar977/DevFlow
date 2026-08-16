import { describe, it, expect } from "vitest";
import { formatTrackedTime, formatElapsed } from "@/features/tasks/lib/trackedTime";

describe("formatTrackedTime", () => {
  it("formats under an hour as minutes only", () => {
    expect(formatTrackedTime(5 * 60)).toBe("5m");
  });

  it("formats an hour and change as Xh Ym", () => {
    expect(formatTrackedTime(90 * 60)).toBe("1h 30m");
  });

  it("rounds down partial minutes", () => {
    expect(formatTrackedTime(125)).toBe("2m");
  });

  it("formats zero as 0m", () => {
    expect(formatTrackedTime(0)).toBe("0m");
  });
});

describe("formatElapsed", () => {
  it("formats zero as 0:00", () => {
    expect(formatElapsed(0)).toBe("0:00");
  });

  it("formats under an hour as M:SS", () => {
    expect(formatElapsed(5 * 60 + 3)).toBe("5:03");
  });

  it("does not overflow minutes past 59 for a multi-hour session", () => {
    // A 6h12m10s forgotten timer must not render as "372:10".
    expect(formatElapsed(6 * 3600 + 12 * 60 + 10)).toBe("6:12:10");
  });

  it("pads minutes and seconds once in H:MM:SS form", () => {
    expect(formatElapsed(3600 + 5 * 60 + 9)).toBe("1:05:09");
  });
});
