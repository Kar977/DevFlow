import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/shared/api/client";
import { PRTrendsSchema } from "@/shared/api/schemas/metrics";

export type { PRTrends, PRTrendPoint } from "@/shared/api/schemas/metrics";

export function usePRTrendsQuery(
  orgId: string | null,
  memberUserId?: string,
  weeks = 12
) {
  return useQuery({
    queryKey: ["metrics", "pr-trends", orgId ?? "", memberUserId ?? "all", weeks],
    enabled: !!orgId,
    queryFn: () =>
      apiClient
        .get("/metrics/pr-trends", {
          params: {
            organization_id: orgId,
            weeks,
            ...(memberUserId ? { member_user_id: memberUserId } : {}),
          },
        })
        .then((r) => PRTrendsSchema.parse(r.data)),
  });
}
