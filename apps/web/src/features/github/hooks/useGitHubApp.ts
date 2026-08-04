import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/shared/api/client";

export interface Installation {
  id: string;
  installation_id: number;
  account_login: string;
  account_type: "User" | "Organization";
  account_avatar_url: string | null;
  repository_selection: "all" | "selected";
  suspended_at: string | null;
  created_at: string;
}

export interface SyncRun {
  id: string;
  status: "running" | "completed" | "failed";
  repos_synced: number;
  prs_synced: number;
  reviews_synced: number;
  error_message: string | null;
  started_at: string;
  finished_at: string | null;
}

export const githubAppQueryKeys = {
  installations: (orgId: string) =>
    ["github-app", "installations", orgId] as const,
  syncRuns: (orgId: string) => ["github-app", "sync-runs", orgId] as const,
};

export function useInstallationsQuery(orgId: string | null) {
  return useQuery({
    queryKey: githubAppQueryKeys.installations(orgId ?? ""),
    enabled: !!orgId,
    queryFn: () =>
      apiClient
        .get("/integrations/github/app/installations", {
          params: { organization_id: orgId },
        })
        .then((r) => r.data as { items: Installation[] }),
  });
}

export function useInstallAppMutation(orgId: string | null) {
  return useMutation({
    mutationFn: () =>
      apiClient
        .post("/integrations/github/app/install-url", {
          organization_id: orgId,
        })
        .then((r) => r.data as { install_url: string }),
    onSuccess: ({ install_url }) => {
      window.location.href = install_url;
    },
  });
}

export function useDisconnectInstallation(orgId: string | null) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (installationUuid: string) =>
      apiClient.delete(
        `/integrations/github/app/installations/${installationUuid}`,
        { params: { organization_id: orgId } }
      ),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["github-app"] });
      qc.invalidateQueries({ queryKey: ["repositories"] });
    },
  });
}

export function useRefreshInstallationRepos(orgId: string | null) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (installationUuid: string) =>
      apiClient
        .post(
          `/integrations/github/app/installations/${installationUuid}/refresh-repos`,
          null,
          { params: { organization_id: orgId } }
        )
        .then((r) => r.data as { repos: number }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["repositories"] });
    },
  });
}

export function useOrgSyncMutation(orgId: string | null) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () =>
      apiClient
        .post("/integrations/github/sync", null, {
          params: { organization_id: orgId },
        })
        .then((r) => r.data as { prs_synced: number; reviews_synced: number }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["github-app", "sync-runs"] });
      qc.invalidateQueries({ queryKey: ["pull-requests"] });
      qc.invalidateQueries({ queryKey: ["metrics"] });
      qc.invalidateQueries({ queryKey: ["repositories"] });
    },
  });
}

export function useSyncRunsQuery(orgId: string | null) {
  return useQuery({
    queryKey: githubAppQueryKeys.syncRuns(orgId ?? ""),
    enabled: !!orgId,
    queryFn: () =>
      apiClient
        .get("/integrations/github/sync-runs", {
          params: { organization_id: orgId },
        })
        .then((r) => r.data as { items: SyncRun[] }),
  });
}
