import { Button, Card, CardContent, CardHeader, CardTitle } from "@/shared/ui";
import type { GitHubStatus } from "@/features/github/hooks/useGitHubStatus";

interface Props {
  status: GitHubStatus | undefined;
  onConnect: () => void;
  onDisconnect: () => void;
  isConnecting: boolean;
  isDisconnecting: boolean;
}

export function ConnectGitHubCard({
  status,
  onConnect,
  onDisconnect,
  isConnecting,
  isDisconnecting,
}: Props) {
  const connected = status?.connected ?? false;

  return (
    <Card>
      <CardHeader>
        <CardTitle>GitHub</CardTitle>
      </CardHeader>
      <CardContent className="flex items-center justify-between gap-4">
        {connected ? (
          <>
            <div className="flex items-center gap-3">
              <div className="flex flex-col">
                <span className="font-medium">{status?.github_login}</span>
                <span className="text-xs text-green-600">Połączono</span>
              </div>
            </div>
            <Button
              variant="outline"
              size="sm"
              onClick={onDisconnect}
              disabled={isDisconnecting}
            >
              {isDisconnecting ? "Rozłączanie..." : "Rozłącz"}
            </Button>
          </>
        ) : (
          <>
            <span className="text-muted-foreground text-sm">
              Połącz konto GitHub, aby synchronizować pull requesty i zadania.
            </span>
            <Button onClick={onConnect} disabled={isConnecting} size="sm">
              {isConnecting ? "Przekierowanie..." : "Połącz GitHub"}
            </Button>
          </>
        )}
      </CardContent>
    </Card>
  );
}
