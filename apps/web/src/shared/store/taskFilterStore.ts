import { create } from "zustand";
import { persist } from "zustand/middleware";

// Same bug, same fix as `projectStore.ts`: TaskListPage's status/assignee
// filters lived in plain `useState`, which is lost every time the `/tasks`
// lazy route unmounts (any navigation away and back). `status` has no
// org-specific meaning (the enum is fixed) so it's stored globally;
// `assigneeId` is keyed per organization like the project selector, since
// a member id only makes sense within the org it belongs to.
type TaskFilterState = {
  status: string;
  assigneeIdByOrg: Record<string, string>;
  // "" = all sprints, "backlog" = unassigned only, else a sprint's start
  // date — keyed per org like assigneeIdByOrg, since a sprint date only
  // means something within the org it belongs to.
  sprintFilterByOrg: Record<string, string>;
};

type TaskFilterActions = {
  setStatus: (status: string) => void;
  setAssignee: (orgId: string, assigneeId: string) => void;
  setSprintFilter: (orgId: string, sprintFilter: string) => void;
};

export const useTaskFilterStore = create<TaskFilterState & TaskFilterActions>()(
  persist(
    (set) => ({
      status: "all",
      assigneeIdByOrg: {},
      sprintFilterByOrg: {},
      setStatus: (status) => set({ status }),
      setAssignee: (orgId, assigneeId) =>
        set((state) => ({
          assigneeIdByOrg: { ...state.assigneeIdByOrg, [orgId]: assigneeId },
        })),
      setSprintFilter: (orgId, sprintFilter) =>
        set((state) => ({
          sprintFilterByOrg: { ...state.sprintFilterByOrg, [orgId]: sprintFilter },
        })),
    }),
    { name: "devflow-task-filters" }
  )
);
