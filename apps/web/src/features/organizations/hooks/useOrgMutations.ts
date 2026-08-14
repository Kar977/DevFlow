import { useMutation, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/shared/api/client";
import { useOrgStore } from "@/shared/store/orgStore";
import { orgQueryKeys } from "./useOrgsQuery";

interface CreateOrganizationData {
  name: string;
  description?: string;
}

interface OrganizationResponse {
  id: string;
  name: string;
  slug: string;
  description: string | null;
}

export function useCreateOrganization() {
  const qc = useQueryClient();
  const { setActiveOrg } = useOrgStore();

  return useMutation({
    mutationFn: (data: CreateOrganizationData) =>
      apiClient
        .post<OrganizationResponse>("/organizations", data)
        .then((r) => r.data),
    onSuccess: (org) => {
      void qc.invalidateQueries({ queryKey: orgQueryKeys.all });
      setActiveOrg(org.id);
    },
  });
}

interface UpdateOrganizationData {
  name?: string;
  description?: string | null;
}

export function useUpdateOrganization(orgId: string) {
  const qc = useQueryClient();

  return useMutation({
    mutationFn: (data: UpdateOrganizationData) =>
      apiClient
        .patch<OrganizationResponse>(`/organizations/${orgId}`, data)
        .then((r) => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: orgQueryKeys.all }),
  });
}
