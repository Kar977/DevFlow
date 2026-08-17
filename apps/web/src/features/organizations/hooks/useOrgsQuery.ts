import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/shared/api/client";
import { OrganizationSchema } from "@/shared/api/schemas/organization";

export const orgQueryKeys = {
  all: ["organizations"] as const,
  list: () => [...orgQueryKeys.all, "list"] as const,
  detail: (id: string) => [...orgQueryKeys.all, "detail", id] as const,
};

export function useOrgsQuery() {
  return useQuery({
    queryKey: orgQueryKeys.list(),
    queryFn: async () => {
      const res = await apiClient.get("/organizations");
      const body = res.data as {
        data: Array<{ id: string; name: string; slug: string }>;
      };
      return { items: body.data };
    },
  });
}

/** Full organization detail, including `description` — the list query above
 * only carries id/name/slug, which isn't enough to build an edit form. */
export function useOrgQuery(orgId: string | null) {
  return useQuery({
    queryKey: orgQueryKeys.detail(orgId ?? ""),
    enabled: !!orgId,
    queryFn: () =>
      apiClient
        .get(`/organizations/${orgId}`)
        .then((r) => OrganizationSchema.parse(r.data)),
  });
}
