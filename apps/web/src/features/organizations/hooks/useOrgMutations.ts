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
