import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/shared/api/client";

export interface GitHubStatus {
  connected: boolean;
  github_login?: string | null;
  github_avatar_url?: string | null;
}

export function useGitHubStatus() {
  return useQuery({
    queryKey: ["github", "status"],
    queryFn: () =>
      apiClient.get("/integrations/github/status").then((r) => r.data as GitHubStatus),
  });
}
