import { useMutation, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/shared/api/client";
import { reportQueryKeys, type ReportType } from "./useReportsQuery";

export function useGenerateReport() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: {
      type: ReportType;
      format: "json";
      project_id?: string;
      organization_id?: string;
    }) => apiClient.post("/reports", data).then((r) => r.data as { id: string }),
    onSuccess: () => qc.invalidateQueries({ queryKey: reportQueryKeys.all }),
  });
}

export function useDeleteReport() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (reportId: string) => apiClient.delete(`/reports/${reportId}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: reportQueryKeys.list() }),
  });
}
