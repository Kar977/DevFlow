export type { User, AccessTokenResponse, LoginRequest, RegisterRequest } from "@/shared/api/schemas/auth";
export type { Organization } from "@/shared/api/schemas/organization";
export type {
  Summary,
  Velocity,
  WeeklyVelocityPoint,
  TimeTracking,
  DailyHours,
  CompletionRate,
  EstimationAccuracy,
  Streak,
  PRDashboard,
  PRDashboardMember,
  PRTrends,
  PRTrendPoint,
} from "@/shared/api/schemas/metrics";

export type ApiError = {
  detail: string;
  status: number;
};
