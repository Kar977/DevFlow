import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { daysAgoLocal, toLocalDateString, todayLocal } from "@/shared/lib/localDate";

// Pinned to a non-UTC zone so the UTC-vs-local divergence this module exists
// to fix is actually exercised, regardless of the test runner's own TZ.
const ORIGINAL_TZ = process.env.TZ;

beforeEach(() => {
  process.env.TZ = "Europe/Warsaw";
});

afterEach(() => {
  process.env.TZ = ORIGINAL_TZ;
  vi.useRealTimers();
});

describe("toLocalDateString", () => {
  it("formats local calendar fields, not UTC ones", () => {
    // 23:30 UTC on Aug 16 is already 01:30 local (CEST, UTC+2) on Aug 17.
    const instant = new Date("2026-08-16T23:30:00Z");
    expect(toLocalDateString(instant)).toBe("2026-08-17");
    expect(instant.toISOString().split("T")[0]).toBe("2026-08-16");
  });

  it("pads single-digit month and day", () => {
    const instant = new Date(2026, 0, 5); // local Jan 5, 2026
    expect(toLocalDateString(instant)).toBe("2026-01-05");
  });
});

describe("todayLocal", () => {
  it("names the local day, not the UTC day, near a UTC midnight boundary", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-08-16T23:30:00Z"));

    expect(todayLocal()).toBe("2026-08-17");
  });
});

describe("daysAgoLocal", () => {
  it("subtracts whole local calendar days", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-08-17T10:00:00Z")); // 12:00 local (CEST)

    expect(daysAgoLocal(0)).toBe("2026-08-17");
    expect(daysAgoLocal(30)).toBe("2026-07-18");
  });
});
