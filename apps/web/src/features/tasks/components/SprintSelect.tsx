import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/shared/ui";
import { useOrgSprintsQuery } from "@/features/organizations/hooks/useOrgSprints";
import { formatSprintDate, formatSprintLabel } from "@/features/organizations/lib/sprintFormat";
import { useOrgStore } from "@/shared/store/orgStore";

const BACKLOG = "__backlog__";

interface Props {
  /** "" = backlog, else a YYYY-MM-DD sprint start date. */
  value: string;
  onChange: (value: string) => void;
  id?: string;
  disabled?: boolean;
}

/**
 * Sprint picker shared by CreateTaskModal and TaskDetailModal. Options come
 * from `GET /organizations/{id}/sprints` — never re-derive sprint dates
 * here, that math lives on the backend (core.services.period.sprint_series).
 *
 * When `value` is a date that isn't in the current series (the org's
 * cadence changed since the task was assigned), an extra "poza kadencją"
 * option is added so the select can still show it — the alternative,
 * silently falling back to some other option, would rewrite the task's
 * sprint out from under whoever's just trying to edit something else.
 */
export function SprintSelect({ value, onChange, id, disabled }: Props) {
  const activeOrgId = useOrgStore((s) => s.activeOrgId);
  const { data: sprints } = useOrgSprintsQuery(activeOrgId, { back: 3, forward: 6 });

  const isOrphaned =
    value !== "" && sprints !== undefined && !sprints.some((s) => s.start_date === value);

  return (
    <Select
      value={value === "" ? BACKLOG : value}
      onValueChange={(v) => onChange(v === BACKLOG ? "" : v)}
      disabled={disabled || sprints?.length === 0}
    >
      <SelectTrigger id={id} aria-label="Sprint">
        <SelectValue />
      </SelectTrigger>
      <SelectContent>
        <SelectItem value={BACKLOG}>Backlog</SelectItem>
        {isOrphaned && (
          <SelectItem value={value}>
            Poza kadencją ({formatSprintDate(value)})
          </SelectItem>
        )}
        {sprints?.map((sprint) => (
          <SelectItem key={sprint.start_date} value={sprint.start_date}>
            {formatSprintLabel(sprint)}
            {sprint.is_current ? " · bieżący" : ""}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}
