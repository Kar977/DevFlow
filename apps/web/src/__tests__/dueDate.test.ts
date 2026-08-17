import { describe, it, expect } from "vitest";
import { toDueDateIso, fromDueDateIso, isOverdue } from "@/features/tasks/lib/dueDate";

describe("toDueDateIso / fromDueDateIso", () => {
  it("round-trips a local calendar date", () => {
    const iso = toDueDateIso("2026-08-20");
    expect(fromDueDateIso(iso)).toBe("2026-08-20");
  });

  it("encodes the end of the local day, not its start", () => {
    const iso = toDueDateIso("2026-08-20");
    const date = new Date(iso);
    expect(date.getHours()).toBe(23);
    expect(date.getMinutes()).toBe(59);
  });

  it("round-trips dates at both ends of the year", () => {
    expect(fromDueDateIso(toDueDateIso("2026-01-01"))).toBe("2026-01-01");
    expect(fromDueDateIso(toDueDateIso("2026-12-31"))).toBe("2026-12-31");
  });
});

describe("isOverdue", () => {
  it("is false when there is no due date", () => {
    expect(isOverdue({ due_date: null, status: "todo" })).toBe(false);
  });

  it("is true for a past due date on an open task", () => {
    const past = new Date(Date.now() - 86_400_000).toISOString();
    expect(isOverdue({ due_date: past, status: "todo" })).toBe(true);
  });

  it("is false for a future due date", () => {
    const future = new Date(Date.now() + 86_400_000).toISOString();
    expect(isOverdue({ due_date: future, status: "todo" })).toBe(false);
  });

  it("is false for a done task even if the due date has passed", () => {
    const past = new Date(Date.now() - 86_400_000).toISOString();
    expect(isOverdue({ due_date: past, status: "done" })).toBe(false);
  });

  it("is false for a cancelled task even if the due date has passed", () => {
    const past = new Date(Date.now() - 86_400_000).toISOString();
    expect(isOverdue({ due_date: past, status: "cancelled" })).toBe(false);
  });
});
