import { describe, it, expect, beforeEach } from "vitest";
import { useTaskFilterStore } from "@/shared/store/taskFilterStore";

beforeEach(() => {
  localStorage.clear();
  useTaskFilterStore.setState({ status: "all", assigneeIdByOrg: {} });
});

describe("useTaskFilterStore", () => {
  it("starts with status 'all' and no assignee for any org", () => {
    expect(useTaskFilterStore.getState().status).toBe("all");
    expect(useTaskFilterStore.getState().assigneeIdByOrg).toEqual({});
  });

  it("setStatus updates the global status filter", () => {
    useTaskFilterStore.getState().setStatus("done");
    expect(useTaskFilterStore.getState().status).toBe("done");
  });

  it("setAssignee records the assignee under its org", () => {
    useTaskFilterStore.getState().setAssignee("org-1", "user-1");
    expect(useTaskFilterStore.getState().assigneeIdByOrg).toEqual({ "org-1": "user-1" });
  });

  it("keeps separate assignee selections per organization", () => {
    useTaskFilterStore.getState().setAssignee("org-1", "user-1");
    useTaskFilterStore.getState().setAssignee("org-2", "user-2");
    expect(useTaskFilterStore.getState().assigneeIdByOrg).toEqual({
      "org-1": "user-1",
      "org-2": "user-2",
    });
  });

  it("persists to localStorage under the devflow-task-filters key", () => {
    useTaskFilterStore.getState().setStatus("in_progress");
    useTaskFilterStore.getState().setAssignee("org-1", "user-1");
    const raw = localStorage.getItem("devflow-task-filters");
    expect(raw).not.toBeNull();
    const parsed = JSON.parse(raw as string);
    expect(parsed.state.status).toBe("in_progress");
    expect(parsed.state.assigneeIdByOrg).toEqual({ "org-1": "user-1" });
  });
});
