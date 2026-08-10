import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/shared/api/client";
import {
  PRDashboardSchema,
  PRDashboardMembersSchema,
} from "@/shared/api/schemas/metrics";

export type { PRDashboard, PRDashboardMember } from "@/shared/api/schemas/metrics";

export function usePRDashboardQuery(
  orgId: string | null,
  memberUserId?: string
) {
  return useQuery({
    queryKey: ["metrics", "pr-dashboard", orgId ?? "", memberUserId ?? "all"],
    enabled: !!orgId,
    queryFn: () =>
      apiClient
        .get("/metrics/pr-dashboard", {
          params: {
            organization_id: orgId,
            ...(memberUserId ? { member_user_id: memberUserId } : {}),
          },
        })
        .then((r) => PRDashboardSchema.parse(r.data)),
  });
}

export function usePRDashboardMembersQuery(orgId: string | null) {
  return useQuery({
    queryKey: ["metrics", "pr-dashboard-members", orgId ?? ""],
    enabled: !!orgId,
    queryFn: () =>
      apiClient
        .get("/metrics/pr-dashboard/members", {
          params: { organization_id: orgId },
        })
        .then((r) => {
          const body = PRDashboardMembersSchema.parse(r.data);
          return { items: body.data };
        }),
  });
}
