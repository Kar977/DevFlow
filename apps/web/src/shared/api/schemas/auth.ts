import { z } from "zod";

export const UserSchema = z.object({
  id: z.string().uuid(),
  email: z.string().email(),
  full_name: z.string().nullable(),
  avatar_url: z.string().url().nullable(),
  created_at: z.string().datetime(),
  updated_at: z.string().datetime(),
});

export const TokenResponseSchema = z.object({
  access_token: z.string(),
  refresh_token: z.string(),
  token_type: z.literal("bearer"),
});

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
export type TokenResponse = z.infer<typeof TokenResponseSchema>;
export type AccessTokenResponse = z.infer<typeof AccessTokenResponseSchema>;
export type LoginRequest = z.infer<typeof LoginRequestSchema>;
export type RegisterRequest = z.infer<typeof RegisterRequestSchema>;
