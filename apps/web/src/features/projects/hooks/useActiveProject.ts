import { useEffect } from "react";
import { useOrgStore } from "@/shared/store/orgStore";
import { useProjectStore } from "@/shared/store/projectStore";
import { useProjectsQuery } from "./useProjectsQuery";

/**
 * The currently selected project on the Tasks page, persisted per
 * organization (`shared/store/projectStore`) instead of component state —
 * component state doesn't survive a route unmount, and `/tasks` is a
 * `lazy()` route that unmounts on every navigation away from it.
 *
 * Mirrors `OrgSwitcher`'s validate-then-fallback pattern: the stored id is
 * only trusted if it's actually in the fetched project list (covers a
 * stale id from a deleted project, or one belonging to a different org);
 * otherwise it falls back to the first project. `activeProjectId` is
 * derived synchronously from render state rather than mirrored into
 * `useState`, so the very first render after an org switch never hands a
 * stale, cross-org project id to a query.
 */
export function useActiveProject() {
  const { activeOrgId } = useOrgStore();
  const activeProjectIdByOrg = useProjectStore((s) => s.activeProjectIdByOrg);
  const setActiveProjectInStore = useProjectStore((s) => s.setActiveProject);
  const projectsQuery = useProjectsQuery();
  const items = projectsQuery.data?.items ?? [];

  const stored = activeOrgId ? activeProjectIdByOrg[activeOrgId] : undefined;
  const storedIsValid = !!stored && items.some((p) => p.id === stored);
  const activeProjectId = storedIsValid ? (stored as string) : "";

  useEffect(() => {
    if (!activeOrgId || items.length === 0) return;
    const isValid = stored && items.some((p) => p.id === stored);
    if (!isValid) setActiveProjectInStore(activeOrgId, items[0].id);
  }, [activeOrgId, items, stored, setActiveProjectInStore]);

  function setActiveProject(projectId: string) {
    if (activeOrgId) setActiveProjectInStore(activeOrgId, projectId);
  }

  return {
    activeProjectId,
    setActiveProject,
    projects: projectsQuery.data,
    isLoading: projectsQuery.isLoading,
  };
}
