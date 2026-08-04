import { describe, it, expect } from "vitest";
import { formatTrackedTime } from "@/features/tasks/lib/trackedTime";

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
