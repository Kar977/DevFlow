import { Button, Card, CardContent, CardHeader, CardTitle } from "@/shared/ui";
import type { Installation } from "@/features/github/hooks/useGitHubApp";

interface Props {
  installations: Installation[];
  isAdmin: boolean;
  onInstall: () => void;
  onDisconnect: (installationUuid: string) => void;
  onRefreshRepos: (installationUuid: string) => void;
  isInstalling: boolean;
  isDisconnecting: boolean;
  isRefreshing: boolean;
}

export function InstallationList({
  installations,
  isAdmin,
  onInstall,
  onDisconnect,
  onRefreshRepos,
  isInstalling,
  isDisconnecting,
  isRefreshing,
}: Props) {
  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle>GitHub App</CardTitle>
        {isAdmin && (
          <Button size="sm" onClick={onInstall} disabled={isInstalling}>
            {isInstalling ? "Przekierowanie..." : "Zainstaluj GitHub App"}
          </Button>
        )}
      </CardHeader>
      <CardContent>
        {installations.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            Brak instalacji. Zainstaluj aplikację GitHub na koncie osobistym lub
            organizacji GitHub, aby podłączyć repozytoria.
          </p>
        ) : (
          <ul className="space-y-3">
            {installations.map((inst) => (
              <li
                key={inst.id}
                className="flex items-center justify-between gap-4"
              >
                <div className="flex items-center gap-3">
                  {inst.account_avatar_url && (
                    <img
                      src={inst.account_avatar_url}
                      alt=""
                      className="h-8 w-8 rounded-full"
                    />
                  )}
                  <div className="flex flex-col">
                    <span className="font-medium">{inst.account_login}</span>
                    <span className="text-xs text-muted-foreground">
                      {inst.account_type === "Organization"
                        ? "Organizacja GitHub"
                        : "Konto osobiste"}
                      {" · "}
                      {inst.repository_selection === "all"
                        ? "wszystkie repozytoria"
                        : "wybrane repozytoria"}
                      {inst.suspended_at && (
                        <span className="text-destructive"> · zawieszona</span>
                      )}
                    </span>
                  </div>
                </div>
                {isAdmin && (
                  <div className="flex gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => onRefreshRepos(inst.id)}
                      disabled={isRefreshing}
                    >
                      Odśwież repo
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => onDisconnect(inst.id)}
                      disabled={isDisconnecting}
                    >
                      Odłącz
                    </Button>
                  </div>
                )}
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}
