import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/shared/api/client";

export interface Report {
  id: string;
  type: "weekly_summary" | "project_status" | "productivity_overview";
  format: "json";
  status: "pending" | "generating" | "ready" | "failed";
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

export function useReportsQuery() {
  return useQuery({
    queryKey: reportQueryKeys.list(),
    queryFn: () =>
      apiClient.get("/reports").then((r) => r.data as { items: Report[]; total: number }),
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
