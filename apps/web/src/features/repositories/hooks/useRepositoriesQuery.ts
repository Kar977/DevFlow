import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/shared/api/client";

export interface Repository {
  full_name: string;
  pr_count: number;
}

export const repoQueryKeys = {
  all: ["repositories"] as const,
  list: () => [...repoQueryKeys.all, "list"] as const,
};

export function useRepositoriesQuery() {
  return useQuery({
    queryKey: repoQueryKeys.list(),
    queryFn: () =>
      apiClient
        .get("/repositories")
        .then((r) => r.data as { items: Repository[] }),
  });
}
