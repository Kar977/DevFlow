import { useMutation, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/shared/api/client";

export function useGitHubMutations() {
  const qc = useQueryClient();

  const authorize = useMutation({
    mutationFn: () =>
      apiClient.post("/integrations/github/authorize").then((r) => r.data as { url: string }),
    onSuccess: ({ url }) => {
      window.location.href = url;
    },
  });

  const disconnect = useMutation({
    mutationFn: () => apiClient.delete("/integrations/github/disconnect"),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["github"] }),
  });

  const sync = useMutation({
    mutationFn: (projectId: string) =>
      apiClient
        .post("/integrations/github/sync", { project_id: projectId })
        .then((r) => r.data as { tasks_created: number; tasks_updated: number }),
  });

  return {
    authorize: authorize.mutate,
    disconnect: disconnect.mutate,
    sync: sync.mutate,
    syncResult: sync.data,
    isSyncing: sync.isPending,
    isAuthorizing: authorize.isPending,
    isDisconnecting: disconnect.isPending,
  };
}
