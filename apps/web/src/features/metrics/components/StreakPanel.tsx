import { Card, CardContent, CardHeader, CardTitle } from "@/shared/ui";

interface Props {
  data?: { current_streak: number; longest_streak: number };
  isLoading?: boolean;
}

export function StreakPanel({ data, isLoading }: Props) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-sm font-medium text-muted-foreground">Streak</CardTitle>
      </CardHeader>
      <CardContent className="space-y-2">
        {isLoading && <p className="text-muted-foreground text-sm">Ładowanie...</p>}
        {data && (
          <>
            <div>
              <p className="text-sm text-muted-foreground">Aktualny streak</p>
              <p className="text-3xl font-bold">{data.current_streak} <span className="text-base font-normal text-muted-foreground">dni</span></p>
            </div>
            <div>
              <p className="text-sm text-muted-foreground">Najdłuższy streak</p>
              <p className="text-xl font-semibold">{data.longest_streak} <span className="text-sm font-normal text-muted-foreground">dni</span></p>
            </div>
          </>
        )}
        {!data && !isLoading && <p className="text-muted-foreground text-sm">Brak danych.</p>}
      </CardContent>
    </Card>
  );
}
