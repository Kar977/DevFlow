import { useMutation, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/shared/api/client";
import { useProjectStore } from "@/shared/store/projectStore";
import { projectQueryKeys, type Project } from "./useProjectsQuery";

export function useCreateProject() {
  const qc = useQueryClient();
  const setActiveProject = useProjectStore((s) => s.setActiveProject);
  return useMutation({
    mutationFn: (data: { name: string; description?: string; github_repo_url?: string; org_id: string }) =>
      apiClient.post("/projects", data).then((r) => r.data as Project),
    onSuccess: (project) => {
      void qc.invalidateQueries({ queryKey: projectQueryKeys.all });
      // A newly created project is the obvious next thing to work in — same
      // courtesy `useOrgMutations`'s org creation gives the org switcher.
      setActiveProject(project.org_id, project.id);
    },
  });
}

export function useArchiveProject() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (projectId: string) => apiClient.delete(`/projects/${projectId}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: projectQueryKeys.all }),
  });
}
