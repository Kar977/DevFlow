export type { User, AccessTokenResponse, LoginRequest, RegisterRequest } from "@/shared/api/schemas/auth";
export type { Organization } from "@/shared/api/schemas/organization";

export type ApiError = {
  detail: string;
  status: number;
};
