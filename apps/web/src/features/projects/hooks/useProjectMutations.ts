import { useMutation, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/shared/api/client";
import { projectQueryKeys } from "./useProjectsQuery";

export function useCreateProject() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: { name: string; description?: string; github_repo_url?: string; org_id: string }) =>
      apiClient.post("/projects", data).then((r) => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: projectQueryKeys.all }),
  });
}

export function useArchiveProject() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (projectId: string) => apiClient.delete(`/projects/${projectId}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: projectQueryKeys.all }),
  });
}
