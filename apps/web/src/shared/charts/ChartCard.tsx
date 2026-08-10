import type { ReactNode } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/shared/ui";

export interface ChartLegendSeries {
  label: string;
  color: string;
}

interface ChartCardProps {
  title: string;
  subtitle?: string;
  /**
   * Legend entries. Rendered by ChartCard itself (never recharts'
   * <Legend/>) so the "relief rule" — series with sub-3:1 contrast (aqua,
   * yellow) must never carry meaning by color alone — is structural rather
   * than something every chart author has to remember. Omitted entirely for
   * a single series (per the palette's series-count rule).
   */
  series?: ChartLegendSeries[];
  isLoading?: boolean;
  isEmpty?: boolean;
  emptyLabel?: string;
  children: ReactNode;
}

/**
 * Shared wrapper for every chart panel: title, optional subtitle, the chart
 * itself, and the loading/empty states that used to be copy-pasted across
 * five panels (`Ładowanie...` / `Brak danych.`).
 */
export function ChartCard({
  title,
  subtitle,
  series,
  isLoading = false,
  isEmpty = false,
  emptyLabel = "Brak danych.",
  children,
}: ChartCardProps) {
  const showLegend = !!series && series.length >= 2;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-sm font-medium text-muted-foreground">
          {title}
        </CardTitle>
        {subtitle && (
          <p className="text-xs text-muted-foreground">{subtitle}</p>
        )}
      </CardHeader>
      <CardContent>
        {isLoading && (
          <p className="text-muted-foreground text-sm">Ładowanie...</p>
        )}
        {!isLoading && isEmpty && (
          <p className="text-muted-foreground text-sm">{emptyLabel}</p>
        )}
        {!isLoading && !isEmpty && (
          <>
            {children}
            {showLegend && (
              <div className="mt-3 flex flex-wrap gap-3">
                {series.map((s) => (
                  <div
                    key={s.label}
                    className="flex items-center gap-1.5 text-xs text-muted-foreground"
                  >
                    <span
                      className="h-2.5 w-2.5 rounded-full"
                      style={{ backgroundColor: s.color }}
                    />
                    {s.label}
                  </div>
                ))}
              </div>
            )}
          </>
        )}
      </CardContent>
    </Card>
  );
}
