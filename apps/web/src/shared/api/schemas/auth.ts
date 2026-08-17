import { z } from "zod";

export const UserSchema = z.object({
  id: z.string().uuid(),
  email: z.string().email(),
  full_name: z.string().nullable(),
  avatar_url: z.string().url().nullable(),
  timezone: z.string().nullable(),
  created_at: z.string().datetime(),
  // The backend's UserResponse never actually returns this field — kept
  // optional rather than required so a real API response still validates.
  updated_at: z.string().datetime().optional(),
});

// Refresh tokens are never returned in the response body — the backend sets
// them as an httpOnly cookie instead (see shared/api/client.ts). Only the
// short-lived access token comes back to JS.
export const AccessTokenResponseSchema = z.object({
  access_token: z.string(),
  token_type: z.literal("bearer"),
});

export const LoginRequestSchema = z.object({
  email: z.string().email("Podaj poprawny adres e-mail"),
  password: z.string().min(1, "Hasło jest wymagane"),
});

export const RegisterRequestSchema = z.object({
  email: z.string().email("Podaj poprawny adres e-mail"),
  password: z.string().min(8, "Hasło musi mieć co najmniej 8 znaków"),
  full_name: z.string().min(1, "Imię i nazwisko jest wymagane"),
});

export type User = z.infer<typeof UserSchema>;
export type AccessTokenResponse = z.infer<typeof AccessTokenResponseSchema>;
export type LoginRequest = z.infer<typeof LoginRequestSchema>;
export type RegisterRequest = z.infer<typeof RegisterRequestSchema>;
