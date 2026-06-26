import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/shared/api/client";

export interface PullRequest {
  id: string;
  github_pr_id: number;
  github_repo_full_name: string;
  number: number;
  title: string;
  author_login: string;
  state: "open" | "closed" | "merged";
  created_at_github: string;
  merged_at: string | null;
  closed_at: string | null;
  first_review_at: string | null;
  html_url: string;
  last_synced_at: string;
}

export interface Review {
  id: string;
  reviewer_login: string;
  state: string;
  submitted_at: string;
}

export interface PullRequestDetail extends PullRequest {
  reviews: Review[];
}

interface PRsParams {
  state?: string;
  author_login?: string;
  repo?: string;
  limit?: number;
  offset?: number;
}

export const prQueryKeys = {
  all: ["pull-requests"] as const,
  list: (params: PRsParams) => [...prQueryKeys.all, "list", params] as const,
  detail: (id: string) => [...prQueryKeys.all, "detail", id] as const,
};

export function usePullRequestsQuery(params: PRsParams = {}) {
  return useQuery({
    queryKey: prQueryKeys.list(params),
    queryFn: () =>
      apiClient
        .get("/pull-requests", { params })
        .then((r) => r.data as { items: PullRequest[]; total: number }),
  });
}

export function usePullRequestDetailQuery(prId: string) {
  return useQuery({
    queryKey: prQueryKeys.detail(prId),
    queryFn: () =>
      apiClient
        .get(`/pull-requests/${prId}`)
        .then((r) => r.data as PullRequestDetail),
    enabled: !!prId,
  });
}
