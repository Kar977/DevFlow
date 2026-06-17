import { describe, it, expect } from "vitest";
import { UserSchema, TokenResponseSchema, LoginRequestSchema } from "@/shared/api/schemas/auth";
import { OrganizationSchema } from "@/shared/api/schemas/organization";

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

describe("TokenResponseSchema", () => {
  it("parses valid token response", () => {
    const raw = { access_token: "aaa", refresh_token: "bbb", token_type: "bearer" as const };
    expect(TokenResponseSchema.parse(raw)).toEqual(raw);
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
