import { create } from "zustand";
import { persist } from "zustand/middleware";

type OrgState = {
  activeOrgId: string | null;
};

type OrgActions = {
  setActiveOrg: (orgId: string | null) => void;
};

export const useOrgStore = create<OrgState & OrgActions>()(
  persist(
    (set) => ({
      activeOrgId: null,
      setActiveOrg: (orgId) => set({ activeOrgId: orgId }),
    }),
    { name: "devflow-active-org" }
  )
);
