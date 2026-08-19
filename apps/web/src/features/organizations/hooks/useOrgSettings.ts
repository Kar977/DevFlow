import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/shared/api/client";

export interface OrgSettingsResponse {
  organization_id: string;
  sprint_length_days: number;
  sprint_anchor_date: string | null;
  stale_pr_threshold_days: number;
}

/** Partial — each settings tab PATCHes only the fields it owns ("Sprinty"
 * sends cadence, "Metryki" sends only the stale-PR threshold); the backend
 * merges omitted fields with their current value rather than replacing. */
export type UpdateOrgSettingsData = Partial<{
  sprint_length_days: number;
  sprint_anchor_date: string | null;
  stale_pr_threshold_days: number;
}>;

const settingsQueryKey = (orgId: string) =>
  ["organizations", orgId, "settings"] as const;

export function useOrgSettingsQuery(orgId: string | null) {
  return useQuery({
    queryKey: settingsQueryKey(orgId ?? ""),
    enabled: !!orgId,
    queryFn: async (): Promise<OrgSettingsResponse> => {
      const res = await apiClient.get(`/organizations/${orgId}/settings`);
      return res.data as OrgSettingsResponse;
    },
  });
}

export function useUpdateOrgSettings(orgId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: UpdateOrgSettingsData) =>
      apiClient
        .patch<OrgSettingsResponse>(`/organizations/${orgId}/settings`, data)
        .then((r) => r.data),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: settingsQueryKey(orgId) });
      // Cadence changes also shift the sprint preview shown in "Sprinty".
      void qc.invalidateQueries({ queryKey: ["organizations", orgId, "sprints"] });
    },
  });
}
