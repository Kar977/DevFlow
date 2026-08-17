import { useState } from "react";
import { useOrgStore } from "@/shared/store/orgStore";
import { useTaskFilterStore } from "@/shared/store/taskFilterStore";
import { useTasksQuery } from "@/features/tasks/hooks/useTasksQuery";
import { useActiveProject } from "@/features/projects/hooks/useActiveProject";
import { useOrgMembersQuery } from "@/features/organizations/hooks/useOrgMembers";
import { TaskCard } from "@/features/tasks/components/TaskCard";
import { TaskFilters } from "@/features/tasks/components/TaskFilters";
import { TaskDetailModal } from "@/features/tasks/components/TaskDetailModal";
import { CreateTaskModal } from "@/features/tasks/components/CreateTaskModal";
import type { Task } from "@/features/tasks/hooks/useTasksQuery";
import { isOverdue } from "@/features/tasks/lib/dueDate";
import {
  Button,
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/shared/ui";

export function TaskListPage() {
  const { activeOrgId } = useOrgStore();
  const statusFilter = useTaskFilterStore((s) => s.status);
  const setStatusFilter = useTaskFilterStore((s) => s.setStatus);
  const assigneeIdByOrg = useTaskFilterStore((s) => s.assigneeIdByOrg);
  const setAssigneeInStore = useTaskFilterStore((s) => s.setAssignee);
  const assigneeFilter = activeOrgId ? (assigneeIdByOrg[activeOrgId] ?? "") : "";
  function setAssigneeFilter(assigneeId: string) {
    if (activeOrgId) setAssigneeInStore(activeOrgId, assigneeId);
  }
  const [overdueOnly, setOverdueOnly] = useState(false);
  const [selectedTask, setSelectedTask] = useState<Task | null>(null);
  const [showCreate, setShowCreate] = useState(false);

  const {
    activeProjectId: selectedProjectId,
    setActiveProject: setSelectedProjectId,
    projects: projectsData,
  } = useActiveProject();
  const { data: members } = useOrgMembersQuery(activeOrgId);

  const { data, isLoading } = useTasksQuery({
    project_id: selectedProjectId,
    status: statusFilter === "all" ? undefined : statusFilter,
    assignee_id: assigneeFilter || undefined,
  });

  if (!activeOrgId) {
    return (
      <div className="space-y-4">
        <h1 className="text-2xl font-semibold">Zadania</h1>
        <p className="text-muted-foreground">Wybierz organizację, aby zobaczyć zadania.</p>
      </div>
    );
  }

  if (projectsData && projectsData.items.length === 0) {
    return (
      <div className="space-y-4">
        <h1 className="text-2xl font-semibold">Zadania</h1>
        <p className="text-muted-foreground">
          Najpierw utwórz projekt, aby dodawać zadania.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Zadania</h1>
        <div className="flex items-center gap-2">
          {projectsData && (
            <Select value={selectedProjectId} onValueChange={setSelectedProjectId}>
              <SelectTrigger className="w-48">
                <SelectValue placeholder="Wybierz projekt" />
              </SelectTrigger>
              <SelectContent>
                {projectsData.items.map((project) => (
                  <SelectItem key={project.id} value={project.id}>
                    {project.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          )}
          <Button onClick={() => setShowCreate(true)} disabled={!selectedProjectId}>
            Nowe zadanie
          </Button>
        </div>
      </div>

      <TaskFilters
        status={statusFilter}
        onStatusChange={setStatusFilter}
        assigneeId={assigneeFilter}
        onAssigneeChange={setAssigneeFilter}
        members={members ?? []}
        overdueOnly={overdueOnly}
        onOverdueOnlyChange={setOverdueOnly}
      />

      {isLoading && <p className="text-muted-foreground">Ładowanie...</p>}

      {data && (
        <div className="flex flex-col gap-3">
          {/* Client-side filter: GET /tasks has no overdue param, and this
              page has no pagination (always fetches the default limit of
              50) — so filtering what's already loaded is exact for what's
              displayed, though a project with >50 tasks could hide overdue
              ones outside that page. */}
          {(() => {
            const visible = overdueOnly ? data.items.filter(isOverdue) : data.items;
            return visible.length === 0 ? (
              <p className="text-muted-foreground py-8 text-center">
                {overdueOnly ? "Brak przeterminowanych zadań." : "Brak zadań."}
              </p>
            ) : (
              visible.map((task) => (
                <TaskCard key={task.id} task={task} onClick={() => setSelectedTask(task)} />
              ))
            );
          })()}
        </div>
      )}

      {selectedTask && (
        <TaskDetailModal
          task={selectedTask}
          open={!!selectedTask}
          onClose={() => setSelectedTask(null)}
        />
      )}

      {selectedProjectId && (
        <CreateTaskModal
          open={showCreate}
          onClose={() => setShowCreate(false)}
          projectId={selectedProjectId}
        />
      )}
    </div>
  );
}
