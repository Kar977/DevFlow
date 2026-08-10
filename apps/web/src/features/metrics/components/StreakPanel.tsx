import { ChartCard } from "@/shared/charts";
import type { Streak } from "@/shared/types";

interface Props {
  data?: Streak;
  isLoading?: boolean;
}

export function StreakPanel({ data, isLoading }: Props) {
  return (
    <ChartCard title="Streak" isLoading={isLoading} isEmpty={!data}>
      {data && (
        <div className="space-y-2">
          <div>
            <p className="text-sm text-muted-foreground">Aktualny streak</p>
            <p className="text-3xl font-bold">
              {data.current_streak}{" "}
              <span className="text-base font-normal text-muted-foreground">dni</span>
            </p>
          </div>
          <div>
            <p className="text-sm text-muted-foreground">Najdłuższy streak</p>
            <p className="text-xl font-semibold">
              {data.longest_streak}{" "}
              <span className="text-sm font-normal text-muted-foreground">dni</span>
            </p>
          </div>
        </div>
      )}
    </ChartCard>
  );
}
