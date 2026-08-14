import type { Task } from "@/features/tasks/hooks/useTasksQuery";
import { useTaskTrackedSeconds } from "@/features/tasks/hooks/useTaskTrackedSeconds";
import { formatTrackedTime } from "@/features/tasks/lib/trackedTime";
import { formatDueDate, isOverdue } from "@/features/tasks/lib/dueDate";
import { useOrgMembersQuery } from "@/features/organizations/hooks/useOrgMembers";
import { useOrgStore } from "@/shared/store/orgStore";
import { TimerButton } from "./TimerButton";

const statusColors: Record<Task["status"], string> = {
  backlog: "bg-slate-100 text-slate-700",
  todo: "bg-blue-100 text-blue-700",
  in_progress: "bg-yellow-100 text-yellow-700",
  review: "bg-purple-100 text-purple-700",
  done: "bg-green-100 text-green-700",
  cancelled: "bg-red-100 text-red-700",
};

const priorityColors: Record<Task["priority"], string> = {
  low: "bg-gray-100 text-gray-600",
  medium: "bg-blue-100 text-blue-600",
  high: "bg-orange-100 text-orange-600",
  critical: "bg-red-100 text-red-600",
};

interface Props {
  task: Task;
  onClick?: () => void;
}

export function TaskCard({ task, onClick }: Props) {
  const trackedSeconds = useTaskTrackedSeconds(task);
  const { activeOrgId } = useOrgStore();
  const { data: members } = useOrgMembersQuery(activeOrgId);
  const assignee = members?.find((m) => m.user_id === task.assignee_id);
  const overdue = isOverdue(task);

  return (
    <div
      className={`flex items-center justify-between rounded-lg border border-border bg-card p-4 hover:bg-accent/50 cursor-pointer transition-colors ${
        overdue ? "border-l-4 border-l-red-400" : ""
      }`}
      onClick={onClick}
    >
      <div className="flex flex-col gap-1 min-w-0">
        <span className="font-medium truncate">{task.title}</span>
        <div className="flex items-center gap-2 flex-wrap">
          <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${statusColors[task.status]}`}>
            {task.status.replace("_", " ")}
          </span>
          <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${priorityColors[task.priority]}`}>
            {task.priority}
          </span>
          {task.estimate_minutes && (
            <span className="text-xs text-muted-foreground">{task.estimate_minutes} min</span>
          )}
          {trackedSeconds > 0 && (
            <span className="text-xs text-muted-foreground">
              ⏱ {formatTrackedTime(trackedSeconds)}
            </span>
          )}
          {task.due_date && (
            <span
              className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                overdue ? "bg-red-100 text-red-700" : "bg-slate-100 text-slate-600"
              }`}
            >
              📅 {formatDueDate(task.due_date)}
            </span>
          )}
          {assignee && (
            <span className="text-xs text-muted-foreground">👤 {assignee.display_name}</span>
          )}
        </div>
      </div>
      <div onClick={(e) => e.stopPropagation()}>
        <TimerButton task={task} />
      </div>
    </div>
  );
}
