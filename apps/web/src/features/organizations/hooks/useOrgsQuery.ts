import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/shared/api/client";

export const orgQueryKeys = {
  all: ["organizations"] as const,
  list: () => [...orgQueryKeys.all, "list"] as const,
};

export function useOrgsQuery() {
  return useQuery({
    queryKey: orgQueryKeys.list(),
    queryFn: async () => {
      const res = await apiClient.get("/organizations");
      return res.data as { items: Array<{ id: string; name: string; slug: string }> };
    },
  });
}
