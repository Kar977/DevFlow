import { create } from "zustand";
import { persist } from "zustand/middleware";

// Keyed per organization: the tasks page's "last selected project" must not
// leak from one org into another when the org switcher changes, and a user
// working across multiple orgs shouldn't have to re-pick a project every
// time they switch back.
type ProjectState = {
  activeProjectIdByOrg: Record<string, string>;
};

type ProjectActions = {
  setActiveProject: (orgId: string, projectId: string) => void;
  clearActiveProject: (orgId: string) => void;
};

export const useProjectStore = create<ProjectState & ProjectActions>()(
  persist(
    (set) => ({
      activeProjectIdByOrg: {},
      setActiveProject: (orgId, projectId) =>
        set((state) => ({
          activeProjectIdByOrg: { ...state.activeProjectIdByOrg, [orgId]: projectId },
        })),
      clearActiveProject: (orgId) =>
        set((state) => {
          const next = { ...state.activeProjectIdByOrg };
          delete next[orgId];
          return { activeProjectIdByOrg: next };
        }),
    }),
    { name: "devflow-active-project" }
  )
);
