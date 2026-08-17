import { describe, it, expect, beforeEach } from "vitest";
import { useProjectStore } from "@/shared/store/projectStore";

beforeEach(() => {
  localStorage.clear();
  useProjectStore.setState({ activeProjectIdByOrg: {} });
});

describe("useProjectStore", () => {
  it("starts with no active project for any org", () => {
    expect(useProjectStore.getState().activeProjectIdByOrg).toEqual({});
  });

  it("setActiveProject records the project under its org", () => {
    useProjectStore.getState().setActiveProject("org-1", "proj-1");
    expect(useProjectStore.getState().activeProjectIdByOrg).toEqual({ "org-1": "proj-1" });
  });

  it("keeps separate selections per organization", () => {
    useProjectStore.getState().setActiveProject("org-1", "proj-1");
    useProjectStore.getState().setActiveProject("org-2", "proj-2");
    expect(useProjectStore.getState().activeProjectIdByOrg).toEqual({
      "org-1": "proj-1",
      "org-2": "proj-2",
    });
  });

  it("setActiveProject again for the same org overwrites, not appends", () => {
    useProjectStore.getState().setActiveProject("org-1", "proj-1");
    useProjectStore.getState().setActiveProject("org-1", "proj-2");
    expect(useProjectStore.getState().activeProjectIdByOrg).toEqual({ "org-1": "proj-2" });
  });

  it("clearActiveProject removes only that org's entry", () => {
    useProjectStore.getState().setActiveProject("org-1", "proj-1");
    useProjectStore.getState().setActiveProject("org-2", "proj-2");
    useProjectStore.getState().clearActiveProject("org-1");
    expect(useProjectStore.getState().activeProjectIdByOrg).toEqual({ "org-2": "proj-2" });
  });

  it("persists to localStorage under the devflow-active-project key", () => {
    useProjectStore.getState().setActiveProject("org-1", "proj-1");
    const raw = localStorage.getItem("devflow-active-project");
    expect(raw).not.toBeNull();
    const parsed = JSON.parse(raw as string);
    expect(parsed.state.activeProjectIdByOrg).toEqual({ "org-1": "proj-1" });
  });
});
