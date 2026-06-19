import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/shared/api/client";
import { useOrgStore } from "@/shared/store/orgStore";

export interface Project {
  id: string;
  name: string;
  description?: string | null;
  status: "active" | "archived";
  org_id: string;
  github_repo_url?: string | null;
  created_by: string;
  created_at: string;
  updated_at: string;
}

export const projectQueryKeys = {
  all: ["projects"] as const,
  list: (orgId: string) => [...projectQueryKeys.all, "list", orgId] as const,
  detail: (id: string) => [...projectQueryKeys.all, "detail", id] as const,
  metrics: (id: string) => [...projectQueryKeys.all, "metrics", id] as const,
};

export function useProjectsQuery() {
  const { activeOrgId } = useOrgStore();
  return useQuery({
    queryKey: projectQueryKeys.list(activeOrgId ?? ""),
    queryFn: () =>
      apiClient
        .get("/projects", { params: { org_id: activeOrgId } })
        .then((r) => r.data as { items: Project[]; total: number }),
    enabled: !!activeOrgId,
  });
}

export function useProjectMetricsQuery(projectId: string) {
  return useQuery({
    queryKey: projectQueryKeys.metrics(projectId),
    queryFn: () =>
      apiClient
        .get(`/metrics/projects/${projectId}`)
        .then((r) => r.data),
    enabled: !!projectId,
  });
}
