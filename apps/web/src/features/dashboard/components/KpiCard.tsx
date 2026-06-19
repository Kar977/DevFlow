import { Card, CardContent, CardHeader, CardTitle } from "@/shared/ui";

interface Props {
  title: string;
  value: number;
  delta: number;
}

export function KpiCard({ title, value, delta }: Props) {
  const isPositive = delta >= 0;
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-sm font-medium text-muted-foreground">{title}</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="text-2xl font-bold">{value}</div>
        <p className={isPositive ? "text-green-500 text-sm" : "text-red-500 text-sm"}>
          {isPositive ? "+" : ""}{delta.toFixed(1)}%
        </p>
      </CardContent>
    </Card>
  );
}
