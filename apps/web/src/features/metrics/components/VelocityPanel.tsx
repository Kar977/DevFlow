import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer } from "recharts";
import { Card, CardContent, CardHeader, CardTitle } from "@/shared/ui";

interface Props {
  data?: { weeks: Array<{ week: string; tasks_closed: number }>; trend_pct?: number };
  isLoading?: boolean;
}

export function VelocityPanel({ data, isLoading }: Props) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-sm font-medium text-muted-foreground">Velocity (zadania/tydzień)</CardTitle>
      </CardHeader>
      <CardContent>
        {isLoading && <p className="text-muted-foreground text-sm">Ładowanie...</p>}
        {data?.weeks?.length ? (
          <ResponsiveContainer width="100%" height={160}>
            <BarChart data={data.weeks}>
              <XAxis dataKey="week" tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 11 }} />
              <Tooltip />
              <Bar dataKey="tasks_closed" fill="#6366f1" radius={[2, 2, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        ) : (
          !isLoading && <p className="text-muted-foreground text-sm">Brak danych.</p>
        )}
      </CardContent>
    </Card>
  );
}
