import { useGitHubStatus } from "@/features/github/hooks/useGitHubStatus";
import { useGitHubMutations } from "@/features/github/hooks/useGitHubMutations";
import { ConnectGitHubCard } from "@/features/github/components/ConnectGitHubCard";
import { SyncPanel } from "@/features/github/components/SyncPanel";

export function GitHubIntegrationPage() {
  const { data: status, isLoading } = useGitHubStatus();
  const { authorize, disconnect, sync, syncResult, isSyncing, isAuthorizing, isDisconnecting } =
    useGitHubMutations();

  if (isLoading) return <p className="text-muted-foreground">Ładowanie...</p>;

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold">Integracja GitHub</h1>
      <ConnectGitHubCard
        status={status}
        onConnect={authorize}
        onDisconnect={disconnect}
        isConnecting={isAuthorizing}
        isDisconnecting={isDisconnecting}
      />
      {status?.connected && (
        <SyncPanel onSync={sync} isSyncing={isSyncing} syncResult={syncResult} />
      )}
    </div>
  );
}
