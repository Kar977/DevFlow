import { describe, it, expect } from "vitest";
import { GenerateSchema } from "@/features/reports/components/GenerateReportModal";

describe("GenerateSchema", () => {
  it("rejects project_status without a project_id", () => {
    const result = GenerateSchema.safeParse({ type: "project_status" });
    expect(result.success).toBe(false);
    if (!result.success) {
      const issue = result.error.issues[0];
      expect(issue.path).toEqual(["project_id"]);
      expect(issue.message).toBe("Wybierz projekt dla raportu statusu projektu.");
    }
  });

  it("accepts project_status with a project_id", () => {
    const result = GenerateSchema.safeParse({
      type: "project_status",
      project_id: "p1",
    });
    expect(result.success).toBe(true);
  });

  it("does not require project_id for other report types", () => {
    expect(GenerateSchema.safeParse({ type: "weekly_summary" }).success).toBe(
      true
    );
    expect(
      GenerateSchema.safeParse({ type: "productivity_overview" }).success
    ).toBe(true);
  });
});
