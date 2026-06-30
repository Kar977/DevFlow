import { Card, CardContent, CardHeader, CardTitle } from "@/shared/ui";

interface Props {
  data?: {
    sample_size: number;
    accurate_count: number;
    average_ratio: number | null;
  };
  isLoading?: boolean;
}

export function EstimationAccuracyPanel({ data, isLoading }: Props) {
  const accuracyPct =
    data && data.sample_size > 0 ? (data.accurate_count / data.sample_size) * 100 : null;
  const avgOverrunPct =
    data?.average_ratio != null ? (data.average_ratio - 1) * 100 : null;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-sm font-medium text-muted-foreground">Dokładność estymacji</CardTitle>
      </CardHeader>
      <CardContent className="space-y-2">
        {isLoading && <p className="text-muted-foreground text-sm">Ładowanie...</p>}
        {data && data.sample_size > 0 && (
          <>
            <div>
              <p className="text-sm text-muted-foreground">Dokładność</p>
              <p className="text-2xl font-bold">{accuracyPct!.toFixed(1)}%</p>
            </div>
            {avgOverrunPct !== null && (
              <div>
                <p className="text-sm text-muted-foreground">Śr. przekroczenie</p>
                <p className="text-lg font-semibold">{avgOverrunPct.toFixed(1)}%</p>
              </div>
            )}
          </>
        )}
        {(!data || data.sample_size === 0) && !isLoading && (
          <p className="text-muted-foreground text-sm">Brak danych.</p>
        )}
      </CardContent>
    </Card>
  );
}
