import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/shared/api/client";
import { useOrgStore } from "@/shared/store/orgStore";
import { taskQueryKeys, type Task } from "./useTasksQuery";

const BANNER_LIMIT = 5;

/** The caller's own overdue tasks across the active organization — backs the
 * dashboard-wide overdue banner (see OverdueTasksBanner). */
export function useOverdueTasksQuery() {
  const { activeOrgId } = useOrgStore();
  return useQuery({
    queryKey: taskQueryKeys.overdue(activeOrgId ?? ""),
    queryFn: () =>
      apiClient
        .get("/tasks/overdue", {
          params: { organization_id: activeOrgId, limit: BANNER_LIMIT },
        })
        .then((r) => {
          const body = r.data as { data: Task[]; meta: { total: number } };
          return { items: body.data, total: body.meta.total };
        }),
    enabled: !!activeOrgId,
  });
}
