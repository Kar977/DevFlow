import { Card, CardContent, CardHeader, CardTitle } from "@/shared/ui";

interface Props {
  data?: { accuracy_pct: number; avg_over_estimate_pct?: number };
  isLoading?: boolean;
}

export function EstimationAccuracyPanel({ data, isLoading }: Props) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-sm font-medium text-muted-foreground">Dokładność estymacji</CardTitle>
      </CardHeader>
      <CardContent className="space-y-2">
        {isLoading && <p className="text-muted-foreground text-sm">Ładowanie...</p>}
        {data && (
          <>
            <div>
              <p className="text-sm text-muted-foreground">Dokładność</p>
              <p className="text-2xl font-bold">{data.accuracy_pct.toFixed(1)}%</p>
            </div>
            {data.avg_over_estimate_pct !== undefined && (
              <div>
                <p className="text-sm text-muted-foreground">Śr. przekroczenie</p>
                <p className="text-lg font-semibold">{data.avg_over_estimate_pct.toFixed(1)}%</p>
              </div>
            )}
          </>
        )}
        {!data && !isLoading && <p className="text-muted-foreground text-sm">Brak danych.</p>}
      </CardContent>
    </Card>
  );
}
