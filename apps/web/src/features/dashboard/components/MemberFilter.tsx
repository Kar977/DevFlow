export interface MemberFilterItem {
  user_id: string;
  display_name: string;
  disabled?: boolean;
  /** Shown in parens after the name, e.g. "brak konta GitHub". */
  hint?: string;
}

interface Props {
  value: string;
  onChange: (value: string) => void;
  items: MemberFilterItem[] | undefined;
  id?: string;
}

/** Shared "Członek" select — used by both the Flow and Produktywność tabs
 * so the two dashboards no longer disagree on whether a member filter
 * exists at all. Each tab feeds it a different member source (Flow needs
 * a linked GitHub account to attribute PRs; Produktywność works off tasks,
 * so every org member is selectable). */
export function MemberFilter({ value, onChange, items, id = "member-filter" }: Props) {
  return (
    <div className="flex items-center gap-2">
      <label htmlFor={id} className="text-sm text-muted-foreground">
        Członek:
      </label>
      <select
        id={id}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="rounded border border-border bg-background px-3 py-1.5 text-sm"
      >
        <option value="">Cały zespół</option>
        {items?.map((m) => (
          <option key={m.user_id} value={m.user_id} disabled={m.disabled}>
            {m.display_name}
            {m.hint ? ` (${m.hint})` : ""}
          </option>
        ))}
      </select>
    </div>
  );
}
