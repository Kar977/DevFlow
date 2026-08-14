import { isAxiosError } from "axios";
import { useGitHubStatus } from "@/features/github/hooks/useGitHubStatus";
import { useGitHubMutations } from "@/features/github/hooks/useGitHubMutations";
import {
  useDisconnectInstallation,
  useInstallAppMutation,
  useInstallationsQuery,
  useOrgSyncMutation,
  useRefreshInstallationRepos,
  useSyncRunsQuery,
} from "@/features/github/hooks/useGitHubApp";
import {
  useRepositoriesQuery,
  useSetRepositoryTracked,
} from "@/features/repositories/hooks/useRepositoriesQuery";
import { useOrgMembersQuery } from "@/features/organizations/hooks/useOrgMembers";
import { useOrgStore } from "@/shared/store/orgStore";
import { useAuthStore } from "@/shared/store/authStore";
import { ConnectGitHubCard } from "@/features/github/components/ConnectGitHubCard";
import { InstallationList } from "@/features/github/components/InstallationList";
import { RepoPicker } from "@/features/github/components/RepoPicker";
import { SyncPanel } from "@/features/github/components/SyncPanel";

const INSTALL_ERROR_MESSAGES_PL: Record<string, string> = {
  github_app_not_configured:
    "Integracja GitHub App nie jest skonfigurowana na serwerze. Skontaktuj się z administratorem, aby ją uzupełnić.",
  forbidden:
    "Nie masz uprawnień, aby zainstalować GitHub App. Wymagana jest rola właściciela lub administratora organizacji.",
};

function getInstallErrorMessage(error: unknown): string | null {
  if (!error) return null;
  if (isAxiosError(error)) {
    const data = error.response?.data as
      | { error?: { code?: string } }
      | undefined;
    const code = data?.error?.code;
    if (code && code in INSTALL_ERROR_MESSAGES_PL) {
      return INSTALL_ERROR_MESSAGES_PL[code];
    }
  }
  return "Nie udało się rozpocząć instalacji GitHub App.";
}

export function GitHubIntegrationPage() {
  const activeOrgId = useOrgStore((s) => s.activeOrgId);
  const currentUser = useAuthStore((s) => s.user);

  const { data: status, isLoading } = useGitHubStatus();
  const { authorize, disconnect, isAuthorizing, isDisconnecting } =
    useGitHubMutations();

  const { data: members } = useOrgMembersQuery(activeOrgId);
  const myRole = members?.find((m) => m.user_id === currentUser?.id)?.role;
  const isAdmin = myRole === "owner" || myRole === "admin";

  const { data: installations } = useInstallationsQuery(activeOrgId);
  const { data: repos } = useRepositoriesQuery(activeOrgId);
  const { data: syncRuns } = useSyncRunsQuery(activeOrgId);

  const installApp = useInstallAppMutation(activeOrgId);
  const disconnectInstallation = useDisconnectInstallation(activeOrgId);
  const refreshRepos = useRefreshInstallationRepos(activeOrgId);
  const setTracked = useSetRepositoryTracked(activeOrgId);
  const orgSync = useOrgSyncMutation(activeOrgId);

  if (isLoading) return <p className="text-muted-foreground">Ładowanie...</p>;

  const hasInstallation = (installations?.items.length ?? 0) > 0;
  const hasTrackedRepo = repos?.items.some((r) => r.tracked) ?? false;

  return (
    <div className="space-y-4">
      <section className="space-y-2">
        <h2 className="text-lg font-medium">Repozytoria organizacji</h2>
        <InstallationList
          installations={installations?.items ?? []}
          isAdmin={isAdmin}
          onInstall={() => installApp.mutate()}
          onDisconnect={(id) => disconnectInstallation.mutate(id)}
          onRefreshRepos={(id) => refreshRepos.mutate(id)}
          isInstalling={installApp.isPending}
          isDisconnecting={disconnectInstallation.isPending}
          isRefreshing={refreshRepos.isPending}
          installError={getInstallErrorMessage(installApp.error)}
        />
        {hasInstallation && (
          <>
            <RepoPicker
              repositories={repos?.items ?? []}
              isAdmin={isAdmin}
              onToggle={(repoId, tracked) =>
                setTracked.mutate({ repoId, tracked })
              }
              isToggling={setTracked.isPending}
            />
            <SyncPanel
              onSync={() => orgSync.mutate()}
              isSyncing={orgSync.isPending}
              canSync={isAdmin && hasTrackedRepo}
              syncResult={orgSync.data}
              lastRun={syncRuns?.items[0]}
            />
          </>
        )}
      </section>

      <section className="space-y-2">
        <h2 className="text-lg font-medium">Twoja tożsamość GitHub</h2>
        <p className="text-sm text-muted-foreground">
          Powiązanie konta GitHub służy do przypisywania Twoich PR-ów w
          metrykach zespołu.
        </p>
        <ConnectGitHubCard
          status={status}
          onConnect={authorize}
          onDisconnect={disconnect}
          isConnecting={isAuthorizing}
          isDisconnecting={isDisconnecting}
        />
      </section>
    </div>
  );
}
