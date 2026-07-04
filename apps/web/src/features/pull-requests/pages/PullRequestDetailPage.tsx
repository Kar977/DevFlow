import { useParams, Link } from "react-router-dom";
import { ExternalLink } from "lucide-react";
import { usePullRequestDetailQuery } from "../hooks/usePullRequestsQuery";
import { useOrgStore } from "@/shared/store/orgStore";

function stateBadge(state: string) {
  const color =
    state === "open"
      ? "bg-green-100 text-green-800"
      : state === "merged"
        ? "bg-purple-100 text-purple-800"
        : "bg-gray-100 text-gray-800";
  return (
    <span
      className={`inline-flex items-center rounded px-2 py-0.5 text-xs font-medium ${color}`}
    >
      {state}
    </span>
  );
}

function reviewStateBadge(state: string) {
  const color =
    state === "approved"
      ? "bg-green-100 text-green-800"
      : state === "changes_requested"
        ? "bg-red-100 text-red-800"
        : "bg-gray-100 text-gray-800";
  return (
    <span
      className={`inline-flex items-center rounded px-2 py-0.5 text-xs font-medium ${color}`}
    >
      {state.replace("_", " ")}
    </span>
  );
}

function fmtDate(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString("pl-PL", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function PullRequestDetailPage() {
  const { prId } = useParams<{ prId: string }>();
  const activeOrgId = useOrgStore((s) => s.activeOrgId);
  const {
    data: pr,
    isLoading,
    isError,
  } = usePullRequestDetailQuery(activeOrgId, prId ?? "");

  if (isLoading) {
    return <div className="p-8 text-muted-foreground">Ładowanie...</div>;
  }

  if (isError || !pr) {
    return (
      <div className="p-8">
        <p className="text-destructive">Pull request nie znaleziony.</p>
        <Link to="/pull-requests" className="mt-4 inline-block text-sm underline">
          ← Wróć do listy
        </Link>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <Link to="/pull-requests" className="text-sm text-muted-foreground hover:underline">
          ← Pull Requests
        </Link>
      </div>

      <div className="rounded-lg border border-border bg-card p-6">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h1 className="text-xl font-semibold">{pr.title}</h1>
            <p className="mt-1 text-sm text-muted-foreground">
              {pr.repository_full_name} #{pr.number} · autor: {pr.author_login}
            </p>
          </div>
          <div className="flex items-center gap-2">
            {stateBadge(pr.state)}
            <a
              href={pr.html_url}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-1 text-sm text-muted-foreground hover:underline"
            >
              GitHub <ExternalLink className="h-3 w-3" />
            </a>
          </div>
        </div>
      </div>

      <div className="rounded-lg border border-border bg-card p-6">
        <h2 className="mb-4 text-sm font-semibold uppercase tracking-wide text-muted-foreground">
          Timeline
        </h2>
        <ol className="space-y-3 text-sm">
          <li className="flex gap-3">
            <span className="mt-0.5 h-2 w-2 flex-none rounded-full bg-blue-500" />
            <div>
              <p className="font-medium">Otwarty</p>
              <p className="text-muted-foreground">{fmtDate(pr.created_at_github)}</p>
            </div>
          </li>
          <li className="flex gap-3">
            <span className="mt-0.5 h-2 w-2 flex-none rounded-full bg-yellow-500" />
            <div>
              <p className="font-medium">Pierwsze review</p>
              <p className="text-muted-foreground">
                {pr.first_review_at ? fmtDate(pr.first_review_at) : "Brak"}
              </p>
            </div>
          </li>
          <li className="flex gap-3">
            <span className="mt-0.5 h-2 w-2 flex-none rounded-full bg-purple-500" />
            <div>
              <p className="font-medium">
                {pr.state === "merged" ? "Merged" : pr.state === "closed" ? "Closed" : "Otwarty"}
              </p>
              <p className="text-muted-foreground">
                {pr.merged_at
                  ? fmtDate(pr.merged_at)
                  : pr.closed_at
                    ? fmtDate(pr.closed_at)
                    : "—"}
              </p>
            </div>
          </li>
        </ol>
      </div>

      {pr.reviews.length > 0 && (
        <div className="rounded-lg border border-border bg-card p-6">
          <h2 className="mb-4 text-sm font-semibold uppercase tracking-wide text-muted-foreground">
            Reviews ({pr.reviews.length})
          </h2>
          <ul className="space-y-3">
            {pr.reviews.map((review) => (
              <li key={review.id} className="flex items-center gap-3 text-sm">
                <div className="flex h-7 w-7 flex-none items-center justify-center rounded-full bg-muted font-medium text-xs uppercase">
                  {review.reviewer_login[0]}
                </div>
                <div className="flex-1">
                  <span className="font-medium">{review.reviewer_login}</span>
                  <span className="ml-2 text-muted-foreground">{fmtDate(review.submitted_at)}</span>
                </div>
                {reviewStateBadge(review.state)}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
