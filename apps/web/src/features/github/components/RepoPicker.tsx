import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/shared/ui";
import type { Repository } from "@/features/repositories/hooks/useRepositoriesQuery";

interface Props {
  repositories: Repository[];
  isAdmin: boolean;
  onToggle: (repoId: string, tracked: boolean) => void;
  isToggling: boolean;
}

export function RepoPicker({ repositories, isAdmin, onToggle, isToggling }: Props) {
  const [search, setSearch] = useState("");

  const filtered = repositories.filter((repo) =>
    repo.full_name.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <Card>
      <CardHeader>
        <CardTitle>Śledzone repozytoria</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <input
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Szukaj repozytorium..."
          className="w-full rounded border border-border bg-background px-3 py-1.5 text-sm"
        />
        {filtered.length === 0 ? (
          <p className="py-4 text-center text-sm text-muted-foreground">
            {repositories.length === 0
              ? "Brak dostępnych repozytoriów — zainstaluj GitHub App."
              : "Brak wyników."}
          </p>
        ) : (
          <ul className="divide-y divide-border">
            {filtered.map((repo) => (
              <li
                key={repo.id}
                className="flex items-center justify-between gap-4 py-2"
              >
                <div className="flex flex-col">
                  <span className="text-sm font-medium">{repo.full_name}</span>
                  <span className="text-xs text-muted-foreground">
                    {repo.private ? "prywatne" : "publiczne"}
                    {repo.last_synced_at &&
                      ` · sync: ${new Date(repo.last_synced_at).toLocaleString("pl-PL")}`}
                  </span>
                </div>
                <label className="flex items-center gap-2 text-sm">
                  <input
                    type="checkbox"
                    checked={repo.tracked}
                    disabled={!isAdmin || isToggling}
                    onChange={(e) => onToggle(repo.id, e.target.checked)}
                    aria-label={`Śledź ${repo.full_name}`}
                  />
                  Śledź
                </label>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}
