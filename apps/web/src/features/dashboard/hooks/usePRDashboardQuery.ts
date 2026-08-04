import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/shared/api/client";

export interface PRDashboard {
  stale_pr_count: number;
  time_to_first_review: number | null;
  review_velocity: number | null;
  weekly_throughput: number;
  review_ratio: number | null;
}

export interface PRDashboardMember {
  user_id: string;
  display_name: string;
  github_login: string | null;
}

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
        .then((r) => r.data as PRDashboard),
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
          const body = r.data as { data: PRDashboardMember[] };
          return { items: body.data };
        }),
  });
}
