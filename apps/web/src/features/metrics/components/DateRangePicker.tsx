import { useState } from "react";
import { Button, Label, Input } from "@/shared/ui";

interface DateRange {
  date_from: string;
  date_to: string;
}

interface Props {
  initialDateFrom?: string;
  initialDateTo?: string;
  onApply: (range: DateRange) => void;
}

export function DateRangePicker({ initialDateFrom, initialDateTo, onApply }: Props) {
  const [dateFrom, setDateFrom] = useState(initialDateFrom ?? "");
  const [dateTo, setDateTo] = useState(initialDateTo ?? "");

  function handleApply() {
    if (dateFrom && dateTo) {
      onApply({ date_from: dateFrom, date_to: dateTo });
    }
  }

  return (
    <div className="flex items-end gap-4 flex-wrap">
      <div className="flex flex-col gap-1.5">
        <Label htmlFor="date-from">Od</Label>
        <Input
          id="date-from"
          type="date"
          value={dateFrom}
          onChange={(e) => setDateFrom(e.target.value)}
          className="w-44"
        />
      </div>
      <div className="flex flex-col gap-1.5">
        <Label htmlFor="date-to">Do</Label>
        <Input
          id="date-to"
          type="date"
          value={dateTo}
          onChange={(e) => setDateTo(e.target.value)}
          className="w-44"
        />
      </div>
      <Button onClick={handleApply} disabled={!dateFrom || !dateTo}>
        Zastosuj
      </Button>
    </div>
  );
}
