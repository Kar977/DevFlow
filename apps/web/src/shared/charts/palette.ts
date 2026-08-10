// Validated chart palette — see the `dataviz` skill's palette validator.
// Ran against the app's actual card surface (#ffffff, light mode): ALL
// CHECKS PASS, with a contrast WARN on slots 3 (aqua) and 4 (yellow) — both
// sit below 3:1 on white, so any chart using them MUST carry a visible
// legend/direct labels (never color alone). `ChartCard` owns the legend so
// this "relief rule" is structural rather than per-chart discipline.
//
// Dark-mode steps are included but dormant: `darkMode: ["class"]` is
// configured in tailwind.config.ts, but there is no `.dark` block in
// index.css and no theme toggle yet. `useChartPalette()` is the single seam
// — wiring dark mode later means updating this hook, not every chart.

export const CHART_SERIES_LIGHT = [
  "#2a78d6", // slot 1 — blue
  "#eb6834", // slot 2 — orange
  "#1baf7a", // slot 3 — aqua (WARN: 2.82:1 on white — needs legend/labels)
  "#eda100", // slot 4 — yellow (WARN: 2.17:1 on white — needs legend/labels)
] as const;

export const CHART_SERIES_DARK = [
  "#3987e5",
  "#d95926",
  "#199e70",
  "#c98500",
] as const;

export const CHART_CHROME_LIGHT = {
  axis: "#898781",
  grid: "#e1e0d9",
  neutral: "#e1e0d9",
} as const;

export const CHART_CHROME_DARK = {
  axis: "#898781",
  grid: "#2c2c2a",
  neutral: "#2c2c2a",
} as const;

export interface ChartPalette {
  series: {
    primary: string;
    secondary: string;
    tertiary: string;
    quaternary: string;
  };
  chrome: { axis: string; grid: string; neutral: string };
  completion: { done: string; open: string; cancelled: string };
  estimation: { over: string; accurate: string; under: string };
}

/**
 * Charts must call this hook (never import the palette constants directly)
 * — it is the only seam a future dark-mode toggle needs to touch.
 */
export function useChartPalette(): ChartPalette {
  const series = CHART_SERIES_LIGHT;
  const chrome = CHART_CHROME_LIGHT;
  return {
    series: {
      primary: series[0],
      secondary: series[1],
      tertiary: series[2],
      quaternary: series[3],
    },
    chrome,
    completion: { done: series[0], open: chrome.neutral, cancelled: series[1] },
    estimation: { over: series[0], accurate: chrome.neutral, under: series[1] },
  };
}
