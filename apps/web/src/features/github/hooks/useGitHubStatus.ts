import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/shared/api/client";

interface GitHubConnectionResponse {
  id: string;
  github_user_id: string;
  github_login: string;
  scopes: string;
  connected_at: string;
}

export interface GitHubStatus {
  connected: boolean;
  github_login: string | null;
}

export function useGitHubStatus() {
  return useQuery({
    queryKey: ["github", "status"],
    queryFn: async (): Promise<GitHubStatus> => {
      const r = await apiClient.get("/integrations/github/status");
      const conn = r.data as GitHubConnectionResponse | null;
      return { connected: conn != null, github_login: conn?.github_login ?? null };
    },
  });
}
