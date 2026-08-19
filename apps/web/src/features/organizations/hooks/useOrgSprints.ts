import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/shared/api/client";

export interface Sprint {
  /** 1-based, counting from the org's anchor date. `null` when no cadence
   * is configured — the org is on the plain ISO-week fallback and its
   * windows aren't numbered. */
  number: number | null;
  /** Inclusive calendar dates (YYYY-MM-DD). */
  start_date: string;
  end_date: string;
  is_current: boolean;
}

interface SprintListResponse {
  data: Sprint[];
}

const sprintsQueryKey = (orgId: string, back: number, forward: number) =>
  ["organizations", orgId, "sprints", back, forward] as const;

/**
 * The org's sprint series around today — the single source of truth for
 * sprint boundaries. Never re-derive this math on the frontend; always ask
 * the backend (`core.services.period.sprint_series`) for it.
 */
export function useOrgSprintsQuery(
  orgId: string | null,
  opts?: { back?: number; forward?: number }
) {
  const back = opts?.back ?? 6;
  const forward = opts?.forward ?? 2;
  return useQuery({
    queryKey: sprintsQueryKey(orgId ?? "", back, forward),
    enabled: !!orgId,
    staleTime: 5 * 60_000,
    queryFn: async (): Promise<Sprint[]> => {
      const res = await apiClient.get<SprintListResponse>(
        `/organizations/${orgId}/sprints`,
        { params: { back, forward } }
      );
      return res.data.data;
    },
  });
}
