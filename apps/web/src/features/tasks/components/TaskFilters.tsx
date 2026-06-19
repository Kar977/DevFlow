import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/shared/ui";

interface Props {
  status: string;
  onStatusChange: (status: string) => void;
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

export function TaskFilters({ status, onStatusChange }: Props) {
  return (
    <div className="flex items-center gap-4">
      <Select value={status} onValueChange={onStatusChange}>
        <SelectTrigger className="w-48">
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
    </div>
  );
}
