import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/shared/api/client";

export type ReportType =
  | "weekly_summary"
  | "project_status"
  | "productivity_overview"
  | "pr_flow_weekly";

export interface Report {
  id: string;
  type: ReportType;
  format: "json";
  status: "pending" | "generating" | "ready" | "failed";
  organization_id?: string | null;
  payload?: unknown;
  error_message?: string | null;
  generated_at?: string | null;
  created_at: string;
  user_id: string;
}

export const reportQueryKeys = {
  all: ["reports"] as const,
  list: () => [...reportQueryKeys.all, "list"] as const,
  detail: (id: string) => [...reportQueryKeys.all, "detail", id] as const,
};

/** Polls every 3s while any report is still pending/generating, otherwise stops. */
export function getReportsRefetchInterval(items: Report[] | undefined): number | false {
  const active = items?.some(
    (r) => r.status === "pending" || r.status === "generating"
  );
  return active ? 3000 : false;
}

export function useReportsQuery() {
  return useQuery({
    queryKey: reportQueryKeys.list(),
    queryFn: () =>
      apiClient.get("/reports").then((r) => {
        const body = r.data as { data: Report[]; meta: { total: number } };
        return { items: body.data, total: body.meta.total };
      }),
    refetchInterval: (query) => getReportsRefetchInterval(query.state.data?.items),
  });
}

export function useReportPolling(reportId: string | null) {
  return useQuery({
    queryKey: reportQueryKeys.detail(reportId ?? ""),
    queryFn: () =>
      apiClient.get(`/reports/${reportId}`).then((r) => r.data as Report),
    enabled: !!reportId,
    refetchInterval: (query) => {
      const data = query.state.data;
      if (data && (data.status === "ready" || data.status === "failed")) {
        return false;
      }
      return 3000;
    },
  });
}
