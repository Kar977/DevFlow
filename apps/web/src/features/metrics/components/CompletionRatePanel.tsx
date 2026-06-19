import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer } from "recharts";
import { Card, CardContent, CardHeader, CardTitle } from "@/shared/ui";

interface Props {
  data?: { completion_rate: number; completed_tasks: number; total_tasks: number };
  isLoading?: boolean;
}

export function CompletionRatePanel({ data, isLoading }: Props) {
  const done = data?.completed_tasks ?? 0;
  const total = data?.total_tasks ?? 0;
  const remaining = Math.max(0, total - done);
  const pieData = [
    { name: "Ukończone", value: done },
    { name: "Pozostałe", value: remaining },
  ];

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-sm font-medium text-muted-foreground">Completion rate</CardTitle>
      </CardHeader>
      <CardContent>
        {isLoading && <p className="text-muted-foreground text-sm">Ładowanie...</p>}
        {data && (
          <div className="flex items-center gap-4">
            <div className="text-3xl font-bold">{((data.completion_rate ?? 0) * 100).toFixed(0)}%</div>
            <ResponsiveContainer width="100%" height={120}>
              <PieChart>
                <Pie data={pieData} cx="50%" cy="50%" innerRadius={30} outerRadius={50} dataKey="value">
                  <Cell fill="#6366f1" />
                  <Cell fill="#e2e8f0" />
                </Pie>
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
          </div>
        )}
        {!data && !isLoading && <p className="text-muted-foreground text-sm">Brak danych.</p>}
      </CardContent>
    </Card>
  );
}
