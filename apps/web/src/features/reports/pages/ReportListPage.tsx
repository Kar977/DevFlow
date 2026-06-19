import { useState } from "react";
import { Button } from "@/shared/ui";
import { useReportsQuery } from "@/features/reports/hooks/useReportsQuery";
import { ReportsList } from "@/features/reports/components/ReportsList";
import { GenerateReportModal } from "@/features/reports/components/GenerateReportModal";

export function ReportListPage() {
  const [showGenerate, setShowGenerate] = useState(false);
  const { data, isLoading } = useReportsQuery();

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Raporty</h1>
        <Button onClick={() => setShowGenerate(true)}>Nowy raport</Button>
      </div>

      {isLoading && <p className="text-muted-foreground">Ładowanie...</p>}
      {data && <ReportsList reports={data.items} />}

      <GenerateReportModal
        open={showGenerate}
        onClose={() => setShowGenerate(false)}
      />
    </div>
  );
}
