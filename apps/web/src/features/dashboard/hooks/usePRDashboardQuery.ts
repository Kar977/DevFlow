import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/shared/api/client";
import {
  PRDashboardSchema,
  PRDashboardMembersSchema,
} from "@/shared/api/schemas/metrics";
import type { DashboardWindow } from "../lib/period";

export type { PRDashboard, PRDashboardMember } from "@/shared/api/schemas/metrics";

/** @deprecated use `DashboardWindow` from `../lib/period` — kept as an
 * alias so any external imports of the old name keep working. */
export type PRDashboardWindow = DashboardWindow;

export function usePRDashboardQuery(
  orgId: string | null,
  memberUserId?: string,
  window?: DashboardWindow
) {
  return useQuery({
    queryKey: [
      "metrics",
      "pr-dashboard",
      orgId ?? "",
      memberUserId ?? "all",
      window?.date_from ?? "",
      window?.date_to ?? "",
    ],
    // Gated on `window` too: the dashboard always sends an explicit period
    // now (see `DashboardPage`), so firing before it's resolved would just
    // waste a request the org's default-window fallback would answer.
    enabled: !!orgId && !!window,
    queryFn: () =>
      apiClient
        .get("/metrics/pr-dashboard", {
          params: {
            organization_id: orgId,
            ...(memberUserId ? { member_user_id: memberUserId } : {}),
            ...(window?.date_from ? { date_from: window.date_from } : {}),
            ...(window?.date_to ? { date_to: window.date_to } : {}),
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
