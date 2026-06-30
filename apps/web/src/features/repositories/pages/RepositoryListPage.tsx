import { Link } from "react-router-dom";
import { useRepositoriesQuery } from "../hooks/useRepositoriesQuery";

export function RepositoryListPage() {
  const { data, isLoading, isError } = useRepositoriesQuery();

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
          Brak repozytoriów. Uruchom sync GitHub aby zsynchronizować PR-y.
        </p>
      ) : (
        <div className="rounded-lg border border-border">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-left text-muted-foreground">
                <th className="px-4 py-3">Repozytorium</th>
                <th className="px-4 py-3 text-right">Liczba PR</th>
              </tr>
            </thead>
            <tbody>
              {data.items.map((repo) => (
                <tr key={repo.full_name} className="border-b border-border last:border-0">
                  <td className="px-4 py-3">
                    <Link
                      to={`/pull-requests?repo=${encodeURIComponent(repo.full_name)}`}
                      className="font-medium hover:underline"
                    >
                      {repo.full_name}
                    </Link>
                  </td>
                  <td className="px-4 py-3 text-right text-muted-foreground">
                    {repo.pr_count}
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
