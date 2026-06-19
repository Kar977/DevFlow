import { describe, it, expect, beforeEach } from "vitest";
import { useOrgStore } from "@/shared/store/orgStore";

beforeEach(() => {
  useOrgStore.setState({ activeOrgId: null });
});

describe("useOrgStore", () => {
  it("starts with no active org", () => {
    expect(useOrgStore.getState().activeOrgId).toBeNull();
  });

  it("setActiveOrg updates activeOrgId", () => {
    useOrgStore.getState().setActiveOrg("org-123");
    expect(useOrgStore.getState().activeOrgId).toBe("org-123");
  });

  it("setActiveOrg(null) clears active org", () => {
    useOrgStore.getState().setActiveOrg("org-123");
    useOrgStore.getState().setActiveOrg(null);
    expect(useOrgStore.getState().activeOrgId).toBeNull();
  });
});
