import { describe, it, expect } from "vitest";
import { pluralizeTasks } from "@/features/tasks/lib/plural";

describe("pluralizeTasks", () => {
  it("uses the singular form for 1", () => {
    expect(pluralizeTasks(1)).toBe("zadanie");
  });

  it("uses the few-form for 2-4", () => {
    expect(pluralizeTasks(2)).toBe("zadania");
    expect(pluralizeTasks(3)).toBe("zadania");
    expect(pluralizeTasks(4)).toBe("zadania");
  });

  it("uses the many-form for 5-21", () => {
    expect(pluralizeTasks(5)).toBe("zadań");
    expect(pluralizeTasks(0)).toBe("zadań");
    expect(pluralizeTasks(21)).toBe("zadań");
  });

  it("treats the 12-14 teens as an exception to the 2-4 rule", () => {
    expect(pluralizeTasks(12)).toBe("zadań");
    expect(pluralizeTasks(13)).toBe("zadań");
    expect(pluralizeTasks(14)).toBe("zadań");
  });

  it("resumes the few-form for 22-24", () => {
    expect(pluralizeTasks(22)).toBe("zadania");
    expect(pluralizeTasks(24)).toBe("zadania");
  });
});
