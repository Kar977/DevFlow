import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue, Label } from "@/shared/ui";

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
}

const STATUS_OPTIONS = [
  { value: "all", label: "Wszystkie statusy" },
  { value: "backlog", label: "Backlog" },
  { value: "todo", label: "To Do" },
  { value: "in_progress", label: "W toku" },
  { value: "review", label: "Review" },
  { value: "done", label: "Ukończone" },
  { value: "cancelled", label: "Anulowane" },
];

const ALL_ASSIGNEES = "all";

export function TaskFilters({
  status,
  onStatusChange,
  assigneeId,
  onAssigneeChange,
  members,
  overdueOnly,
  onOverdueOnlyChange,
}: Props) {
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
