import { Button, Card, CardContent, CardHeader, CardTitle } from "@/shared/ui";
import type { SyncRun } from "@/features/github/hooks/useGitHubApp";

interface SyncResult {
  prs_synced: number;
  reviews_synced: number;
}

interface Props {
  onSync: () => void;
  isSyncing: boolean;
  canSync: boolean;
  syncResult?: SyncResult;
  lastRun?: SyncRun;
}

function runStatusLabel(run: SyncRun): string {
  if (run.status === "running") return "w trakcie";
  if (run.status === "failed") return `błąd: ${run.error_message ?? "nieznany"}`;
  return `OK — ${run.repos_synced} repo, ${run.prs_synced} PR, ${run.reviews_synced} recenzji`;
}

export function SyncPanel({ onSync, isSyncing, canSync, syncResult, lastRun }: Props) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Synchronizacja</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        <div className="flex items-center gap-3">
          <Button onClick={onSync} disabled={!canSync || isSyncing}>
            {isSyncing ? "Synchronizowanie..." : "Synchronizuj"}
          </Button>
          <span className="text-sm text-muted-foreground">
            Pobiera wszystkie PR-y śledzonych repozytoriów organizacji.
          </span>
        </div>
        {syncResult && (
          <p className="text-sm text-muted-foreground">
            Zsynchronizowano: {syncResult.prs_synced} PR-ów,{" "}
            {syncResult.reviews_synced} recenzji
          </p>
        )}
        {lastRun && (
          <p className="text-xs text-muted-foreground">
            Ostatni sync ({new Date(lastRun.started_at).toLocaleString("pl-PL")}):{" "}
            {runStatusLabel(lastRun)}
          </p>
        )}
      </CardContent>
    </Card>
  );
}
