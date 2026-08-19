import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue, Label } from "@/shared/ui";
import { TASK_STATUS_LABELS } from "@/features/tasks/lib/taskStatusLabels";
import { useOrgSprintsQuery } from "@/features/organizations/hooks/useOrgSprints";
import { formatSprintLabel } from "@/features/organizations/lib/sprintFormat";
import { useOrgStore } from "@/shared/store/orgStore";

interface Member {
  user_id: string;
  display_name: string;
}

interface Props {
  status: string;
  onStatusChange: (status: string) => void;
  assigneeId: string;
  onAssigneeChange: (assigneeId: string) => void;
  members: Member[];
  overdueOnly: boolean;
  onOverdueOnlyChange: (overdueOnly: boolean) => void;
  /** "" = all sprints, "backlog" = unassigned only, else a sprint start date. */
  sprintFilter: string;
  onSprintFilterChange: (sprintFilter: string) => void;
}

const STATUS_OPTIONS = [
  { value: "all", label: "Wszystkie statusy" },
  ...Object.entries(TASK_STATUS_LABELS).map(([value, label]) => ({ value, label })),
];

const ALL_ASSIGNEES = "all";
const ALL_SPRINTS = "__all__";
const BACKLOG = "backlog";

export function TaskFilters({
  status,
  onStatusChange,
  assigneeId,
  onAssigneeChange,
  members,
  overdueOnly,
  onOverdueOnlyChange,
  sprintFilter,
  onSprintFilterChange,
}: Props) {
  const activeOrgId = useOrgStore((s) => s.activeOrgId);
  const { data: sprints } = useOrgSprintsQuery(activeOrgId, { back: 3, forward: 6 });
  return (
    <div className="flex items-center gap-4">
      <Select value={status} onValueChange={onStatusChange}>
        <SelectTrigger className="w-48" aria-label="Filtruj po statusie">
          <SelectValue placeholder="Filtruj po statusie" />
        </SelectTrigger>
        <SelectContent>
          {STATUS_OPTIONS.map((opt) => (
            <SelectItem key={opt.value} value={opt.value}>
              {opt.label}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>

      <Select
        value={assigneeId || ALL_ASSIGNEES}
        onValueChange={(v) => onAssigneeChange(v === ALL_ASSIGNEES ? "" : v)}
      >
        <SelectTrigger className="w-48" aria-label="Filtruj wg osoby">
          <SelectValue placeholder="Filtruj wg osoby" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value={ALL_ASSIGNEES}>Wszyscy</SelectItem>
          {members.map((m) => (
            <SelectItem key={m.user_id} value={m.user_id}>
              {m.display_name}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>

      <Select
        value={sprintFilter || ALL_SPRINTS}
        onValueChange={(v) => onSprintFilterChange(v === ALL_SPRINTS ? "" : v)}
      >
        <SelectTrigger className="w-48" aria-label="Filtruj wg sprintu">
          <SelectValue placeholder="Filtruj wg sprintu" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value={ALL_SPRINTS}>Wszystkie sprinty</SelectItem>
          <SelectItem value={BACKLOG}>Backlog</SelectItem>
          {sprints?.map((sprint) => (
            <SelectItem key={sprint.start_date} value={sprint.start_date}>
              {formatSprintLabel(sprint)}
              {sprint.is_current ? " · bieżący" : ""}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>

      <div className="flex items-center gap-1.5">
        <input
          id="overdue-only"
          type="checkbox"
          className="h-4 w-4 rounded border-input"
          checked={overdueOnly}
          onChange={(e) => onOverdueOnlyChange(e.target.checked)}
        />
        <Label htmlFor="overdue-only" className="cursor-pointer font-normal">
          Tylko przeterminowane
        </Label>
      </div>
    </div>
  );
}
