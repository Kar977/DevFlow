import { useState } from "react";
import { Link } from "react-router-dom";
import { usePullRequestsQuery } from "../hooks/usePullRequestsQuery";
import { useRepositoriesQuery } from "@/features/repositories/hooks/useRepositoriesQuery";
import { Badge } from "@/shared/ui/badge";

function stateBadge(state: string) {
  const color =
    state === "open"
      ? "bg-green-100 text-green-800"
      : state === "merged"
        ? "bg-purple-100 text-purple-800"
        : "bg-gray-100 text-gray-800";
  return <span className={`inline-flex items-center rounded px-2 py-0.5 text-xs font-medium ${color}`}>{state}</span>;
}

function ageLabel(createdAt: string): string {
  const days = Math.floor(
    (Date.now() - new Date(createdAt).getTime()) / 86_400_000
  );
  return days === 0 ? "dziś" : `${days}d temu`;
}

export function PullRequestListPage() {
  const [state, setState] = useState<string>("");
  const [repo, setRepo] = useState<string>("");

  const { data, isLoading, isError } = usePullRequestsQuery({
    state: state || undefined,
    repo: repo || undefined,
  });
  const { data: reposData } = useRepositoriesQuery();

  if (isLoading) {
    return <div className="p-8 text-muted-foreground">Ładowanie...</div>;
  }

  if (isError) {
    return <div className="p-8 text-destructive">Błąd ładowania pull requestów.</div>;
  }

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold">Pull Requests</h1>

      <div className="flex gap-3">
        <select
          value={state}
          onChange={(e) => setState(e.target.value)}
          className="rounded border border-border bg-background px-3 py-1.5 text-sm"
        >
          <option value="">Wszystkie stany</option>
          <option value="open">Open</option>
          <option value="merged">Merged</option>
          <option value="closed">Closed</option>
        </select>

        <select
          value={repo}
          onChange={(e) => setRepo(e.target.value)}
          className="rounded border border-border bg-background px-3 py-1.5 text-sm"
        >
          <option value="">Wszystkie repozytoria</option>
          {reposData?.items.map((r) => (
            <option key={r.full_name} value={r.full_name}>
              {r.full_name}
            </option>
          ))}
        </select>
      </div>

      {!data?.items.length ? (
        <p className="py-8 text-center text-muted-foreground">
          Brak PR-ów. Uruchom sync na stronie GitHub.
        </p>
      ) : (
        <div className="rounded-lg border border-border">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-left text-muted-foreground">
                <th className="px-4 py-3">Tytuł</th>
                <th className="px-4 py-3">Autor</th>
                <th className="px-4 py-3">Repo</th>
                <th className="px-4 py-3">Stan</th>
                <th className="px-4 py-3">Wiek</th>
                <th className="px-4 py-3">1. review</th>
              </tr>
            </thead>
            <tbody>
              {data.items.map((pr) => (
                <tr key={pr.id} className="border-b border-border last:border-0">
                  <td className="px-4 py-3">
                    <Link
                      to={`/pull-requests/${pr.id}`}
                      className="font-medium hover:underline"
                    >
                      {pr.title}
                    </Link>
                  </td>
                  <td className="px-4 py-3 text-muted-foreground">{pr.author_login}</td>
                  <td className="px-4 py-3 text-muted-foreground">{pr.github_repo_full_name}</td>
                  <td className="px-4 py-3">{stateBadge(pr.state)}</td>
                  <td className="px-4 py-3 text-muted-foreground">{ageLabel(pr.created_at_github)}</td>
                  <td className="px-4 py-3 text-muted-foreground">
                    {pr.first_review_at ? ageLabel(pr.first_review_at) : "—"}
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
