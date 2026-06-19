import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer } from "recharts";
import { Card, CardContent, CardHeader, CardTitle } from "@/shared/ui";

interface Props {
  data?: { daily_hours: Array<{ date: string; hours: number }> };
  isLoading?: boolean;
}

export function TimeTrackingPanel({ data, isLoading }: Props) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-sm font-medium text-muted-foreground">Godziny dziennie</CardTitle>
      </CardHeader>
      <CardContent>
        {isLoading && <p className="text-muted-foreground text-sm">Ładowanie...</p>}
        {data?.daily_hours?.length ? (
          <ResponsiveContainer width="100%" height={160}>
            <AreaChart data={data.daily_hours}>
              <XAxis dataKey="date" tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 11 }} />
              <Tooltip />
              <Area type="monotone" dataKey="hours" stroke="#10b981" fill="#10b98120" />
            </AreaChart>
          </ResponsiveContainer>
        ) : (
          !isLoading && <p className="text-muted-foreground text-sm">Brak danych.</p>
        )}
      </CardContent>
    </Card>
  );
}
