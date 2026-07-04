import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/shared/api/client";

export interface Repository {
  id: string;
  github_installation_id: string;
  full_name: string;
  private: boolean;
  default_branch: string | null;
  tracked: boolean;
  last_synced_at: string | null;
}

export const repoQueryKeys = {
  all: ["repositories"] as const,
  list: (orgId: string, tracked?: boolean) =>
    [...repoQueryKeys.all, "list", orgId, tracked ?? "all"] as const,
};

export function useRepositoriesQuery(
  orgId: string | null,
  options: { tracked?: boolean } = {}
) {
  return useQuery({
    queryKey: repoQueryKeys.list(orgId ?? "", options.tracked),
    enabled: !!orgId,
    queryFn: () =>
      apiClient
        .get("/repositories", {
          params: {
            organization_id: orgId,
            ...(options.tracked !== undefined ? { tracked: options.tracked } : {}),
          },
        })
        .then((r) => r.data as { items: Repository[] }),
  });
}

export function useSetRepositoryTracked(orgId: string | null) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ repoId, tracked }: { repoId: string; tracked: boolean }) =>
      apiClient
        .patch(
          `/repositories/${repoId}`,
          { tracked },
          { params: { organization_id: orgId } }
        )
        .then((r) => r.data as Repository),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: repoQueryKeys.all });
    },
  });
}
