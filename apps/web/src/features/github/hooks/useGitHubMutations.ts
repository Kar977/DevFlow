import { useMutation, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/shared/api/client";

export function useGitHubMutations() {
  const qc = useQueryClient();

  const authorize = useMutation({
    mutationFn: () =>
      apiClient
        .post("/integrations/github/authorize")
        .then((r) => r.data as { authorize_url: string }),
    onSuccess: ({ authorize_url }) => {
      window.location.href = authorize_url;
    },
  });

  const disconnect = useMutation({
    mutationFn: () => apiClient.delete("/integrations/github/disconnect"),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["github"] }),
  });

  return {
    authorize: authorize.mutate,
    disconnect: disconnect.mutate,
    isAuthorizing: authorize.isPending,
    isDisconnecting: disconnect.isPending,
    authorizeError: authorize.error,
    disconnectError: disconnect.error,
  };
}
