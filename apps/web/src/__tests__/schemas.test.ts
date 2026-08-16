import { describe, it, expect } from "vitest";
import { UserSchema, AccessTokenResponseSchema, LoginRequestSchema } from "@/shared/api/schemas/auth";
import { OrganizationSchema } from "@/shared/api/schemas/organization";
import { MetricTrendsSchema } from "@/shared/api/schemas/metrics";

describe("UserSchema", () => {
  it("parses valid user", () => {
    const raw = {
      id: "00000000-0000-0000-0000-000000000001",
      email: "test@example.com",
      full_name: "Test User",
      avatar_url: null,
      created_at: "2024-01-01T00:00:00Z",
      updated_at: "2024-01-01T00:00:00Z",
    };
    expect(UserSchema.parse(raw)).toEqual(raw);
  });

  it("rejects invalid email", () => {
    expect(() =>
      UserSchema.parse({
        id: "00000000-0000-0000-0000-000000000001",
        email: "not-an-email",
        full_name: null,
        avatar_url: null,
        created_at: "2024-01-01T00:00:00Z",
        updated_at: "2024-01-01T00:00:00Z",
      })
    ).toThrow();
  });
});

describe("AccessTokenResponseSchema", () => {
  it("parses valid access token response", () => {
    const raw = { access_token: "aaa", token_type: "bearer" as const };
    expect(AccessTokenResponseSchema.parse(raw)).toEqual(raw);
  });
});

describe("LoginRequestSchema", () => {
  it("rejects empty password", () => {
    expect(() =>
      LoginRequestSchema.parse({ email: "a@b.com", password: "" })
    ).toThrow();
  });
});

describe("OrganizationSchema", () => {
  it("parses valid org", () => {
    const raw = {
      id: "00000000-0000-0000-0000-000000000001",
      name: "Acme",
      slug: "acme",
      description: null,
      created_by: "00000000-0000-0000-0000-000000000002",
      created_at: "2024-01-01T00:00:00Z",
      updated_at: "2024-01-01T00:00:00Z",
    };
    expect(OrganizationSchema.parse(raw)).toEqual(raw);
  });
});

describe("MetricTrendsSchema", () => {
  it("parses a series with null points (no sample that week)", () => {
    const raw = {
      period_from: "2026-02-16T00:00:00Z",
      period_to: "2026-08-10T00:00:00Z",
      weeks: 26,
      series: [
        {
          metric_key: "tasks_completed",
          points: [
            { week_start: "2026-08-03", value: 2 },
            { week_start: "2026-08-10", value: null },
          ],
        },
      ],
    };
    expect(MetricTrendsSchema.parse(raw)).toEqual(raw);
  });
});
