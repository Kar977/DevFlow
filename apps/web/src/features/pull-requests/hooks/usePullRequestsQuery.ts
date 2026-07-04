import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/shared/api/client";

export interface PullRequest {
  id: string;
  repository_id: string;
  repository_full_name: string;
  github_pr_id: number;
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
  repository_id?: string;
  limit?: number;
  offset?: number;
}

export const prQueryKeys = {
  all: ["pull-requests"] as const,
  list: (orgId: string, params: PRsParams) =>
    [...prQueryKeys.all, "list", orgId, params] as const,
  detail: (orgId: string, id: string) =>
    [...prQueryKeys.all, "detail", orgId, id] as const,
};

export function usePullRequestsQuery(
  orgId: string | null,
  params: PRsParams = {}
) {
  return useQuery({
    queryKey: prQueryKeys.list(orgId ?? "", params),
    enabled: !!orgId,
    queryFn: () =>
      apiClient
        .get("/pull-requests", {
          params: { organization_id: orgId, ...params },
        })
        .then((r) => r.data as { items: PullRequest[]; total: number }),
  });
}

export function usePullRequestDetailQuery(orgId: string | null, prId: string) {
  return useQuery({
    queryKey: prQueryKeys.detail(orgId ?? "", prId),
    enabled: !!orgId && !!prId,
    queryFn: () =>
      apiClient
        .get(`/pull-requests/${prId}`, {
          params: { organization_id: orgId },
        })
        .then((r) => r.data as PullRequestDetail),
  });
}
