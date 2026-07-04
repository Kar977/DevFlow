import { Link } from "react-router-dom";
import { useRepositoriesQuery } from "../hooks/useRepositoriesQuery";
import { useOrgStore } from "@/shared/store/orgStore";

export function RepositoryListPage() {
  const activeOrgId = useOrgStore((s) => s.activeOrgId);
  const { data, isLoading, isError } = useRepositoriesQuery(activeOrgId);

  if (isLoading) {
    return <div className="p-8 text-muted-foreground">Ładowanie...</div>;
  }

  if (isError) {
    return <div className="p-8 text-destructive">Błąd ładowania repozytoriów.</div>;
  }

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold">Repozytoria</h1>

      {!data?.items.length ? (
        <p className="py-8 text-center text-muted-foreground">
          Brak repozytoriów. Zainstaluj GitHub App w{" "}
          <Link to="/settings/github" className="underline">
            ustawieniach GitHub
          </Link>
          , aby podłączyć repozytoria organizacji.
        </p>
      ) : (
        <div className="rounded-lg border border-border">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-left text-muted-foreground">
                <th className="px-4 py-3">Repozytorium</th>
                <th className="px-4 py-3">Widoczność</th>
                <th className="px-4 py-3">Śledzone</th>
                <th className="px-4 py-3 text-right">Ostatni sync</th>
              </tr>
            </thead>
            <tbody>
              {data.items.map((repo) => (
                <tr key={repo.id} className="border-b border-border last:border-0">
                  <td className="px-4 py-3">
                    <Link
                      to={`/pull-requests?repository_id=${repo.id}`}
                      className="font-medium hover:underline"
                    >
                      {repo.full_name}
                    </Link>
                  </td>
                  <td className="px-4 py-3 text-muted-foreground">
                    {repo.private ? "prywatne" : "publiczne"}
                  </td>
                  <td className="px-4 py-3 text-muted-foreground">
                    {repo.tracked ? "tak" : "nie"}
                  </td>
                  <td className="px-4 py-3 text-right text-muted-foreground">
                    {repo.last_synced_at
                      ? new Date(repo.last_synced_at).toLocaleString("pl-PL")
                      : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
