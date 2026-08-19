import { describe, it, expect, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { http, HttpResponse } from "msw";
import { server } from "./mocks/server";
import { DashboardPage } from "@/features/dashboard/pages/DashboardPage";
import { useOrgStore } from "@/shared/store/orgStore";

const ORG_ID = "org-1";

function renderPage(initialEntry = "/dashboard") {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={[initialEntry]}>
        <Routes>
          <Route path="/dashboard" element={<DashboardPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  );
}

const sprintsFixture = {
  data: [
    {
      number: 11,
      start_date: "2026-07-22",
      end_date: "2026-08-04",
      is_current: false,
    },
    {
      number: 12,
      start_date: "2026-08-05",
      end_date: "2026-08-18",
      is_current: true,
    },
  ],
};

const summaryFixture = {
  period_from: "2026-08-05T00:00:00Z",
  period_to: "2026-08-19T00:00:00Z",
  tasks_completed: { value: 5, prev_value: 3, delta_pct: 66.7 },
  active_hours: { value: 12, prev_value: 10, delta_pct: 20.0 },
};
const velocityFixture = {
  period_from: "2026-08-05T00:00:00Z",
  period_to: "2026-08-19T00:00:00Z",
  total_done: 5,
  weeks: 2,
  average_per_week: 2.5,
  trend_pct: 10.0,
  weekly: [],
};
const timeTrackingFixture = {
  period_from: "2026-08-05T00:00:00Z",
  period_to: "2026-08-19T00:00:00Z",
  total_hours: 10,
  daily: [],
};
const completionRateFixture = {
  period_from: "2026-08-05T00:00:00Z",
  period_to: "2026-08-19T00:00:00Z",
  done: 5,
  cancelled: 0,
  open: 2,
  completion_rate: 0.71,
};
const estimationAccuracyFixture = {
  period_from: "2026-08-05T00:00:00Z",
  period_to: "2026-08-19T00:00:00Z",
  sample_size: 3,
  average_ratio: 1.1,
  accurate_count: 2,
  over_estimated_count: 1,
  under_estimated_count: 0,
};
const prDashboardFixture = {
  period_from: "2026-08-05T00:00:00Z",
  period_to: "2026-08-19T00:00:00Z",
  stale_pr_count: 1,
  stale_threshold_days: 5,
  awaiting_first_review: 2,
  time_to_first_review: 4,
  time_to_first_review_prev: 5,
  review_velocity: 1.2,
  weekly_throughput: 3,
  review_ratio: 0.8,
  cohort_size: 5,
  reviewed_in_cohort: 4,
};

let capturedSummaryDates: { from: string | null; to: string | null } | null;
let capturedPrDashboardDates: { from: string | null; to: string | null } | null;

beforeEach(() => {
  capturedSummaryDates = null;
  capturedPrDashboardDates = null;
  useOrgStore.setState({ activeOrgId: ORG_ID });
  server.use(
    http.get(`*/organizations/${ORG_ID}/members`, () => HttpResponse.json({ data: [] })),
    http.get(`*/organizations/${ORG_ID}/sprints`, () => HttpResponse.json(sprintsFixture)),
    http.get("*/metrics/summary", ({ request }) => {
      const url = new URL(request.url);
      capturedSummaryDates = {
        from: url.searchParams.get("date_from"),
        to: url.searchParams.get("date_to"),
      };
      return HttpResponse.json(summaryFixture);
    }),
    http.get("*/metrics/velocity", () => HttpResponse.json(velocityFixture)),
    http.get("*/metrics/time-tracking", () => HttpResponse.json(timeTrackingFixture)),
    http.get("*/metrics/completion-rate", () => HttpResponse.json(completionRateFixture)),
    http.get("*/metrics/estimation-accuracy", () =>
      HttpResponse.json(estimationAccuracyFixture)
    ),
    http.get("*/metrics/streaks", () =>
      HttpResponse.json({ current_streak: 0, longest_streak: 0 })
    ),
    http.get("*/metrics/pr-dashboard", ({ request }) => {
      const url = new URL(request.url);
      capturedPrDashboardDates = {
        from: url.searchParams.get("date_from"),
        to: url.searchParams.get("date_to"),
      };
      return HttpResponse.json(prDashboardFixture);
    }),
    http.get("*/metrics/pr-dashboard/members", () => HttpResponse.json({ data: [] })),
    http.get("*/metrics/pr-trends", () =>
      HttpResponse.json({ period_from: "", period_to: "", weekly: [] })
    )
  );
});

describe("DashboardPage", () => {
  it("shares one period selector across the Flow and Produktywność tabs", async () => {
    renderPage();
    await waitFor(() =>
      expect(screen.getByLabelText("Okres:")).toBeInTheDocument()
    );
    // The selector sits outside both TabsContent panes — assert it's not
    // duplicated per tab.
    expect(screen.getAllByLabelText("Okres:")).toHaveLength(1);
  });

  it("defaults to the current sprint and sends its dates to both tabs' queries", async () => {
    renderPage();
    await waitFor(() => expect(capturedSummaryDates?.from).toBe("2026-08-05"));
    expect(capturedSummaryDates).toEqual({ from: "2026-08-05", to: "2026-08-18" });
    await waitFor(() => expect(capturedPrDashboardDates?.from).toBe("2026-08-05"));
    expect(capturedPrDashboardDates).toEqual({ from: "2026-08-05", to: "2026-08-18" });
  });

  it("switching to 'Poprzedni sprint' sends the previous sprint's dates to both tabs", async () => {
    renderPage();
    await waitFor(() => expect(capturedSummaryDates?.from).toBe("2026-08-05"));

    await userEvent.selectOptions(
      screen.getByLabelText("Okres:"),
      "Poprzedni sprint"
    );

    await waitFor(() => expect(capturedSummaryDates?.from).toBe("2026-07-22"));
    expect(capturedSummaryDates).toEqual({ from: "2026-07-22", to: "2026-08-04" });
    await waitFor(() => expect(capturedPrDashboardDates?.from).toBe("2026-07-22"));
  });

  it("shows the date range picker for 'Własny zakres'", async () => {
    renderPage();
    await waitFor(() =>
      expect(screen.getByLabelText("Okres:")).toBeInTheDocument()
    );

    await userEvent.selectOptions(screen.getByLabelText("Okres:"), "Własny zakres");

    expect(await screen.findByLabelText("Od")).toBeInTheDocument();
    expect(screen.getByLabelText("Do")).toBeInTheDocument();
  });

  it("disables the sprint options when the org has no cadence configured", async () => {
    server.use(
      http.get(`*/organizations/${ORG_ID}/sprints`, () =>
        HttpResponse.json({
          data: [
            { number: null, start_date: "2026-08-17", end_date: "2026-08-23", is_current: true },
          ],
        })
      )
    );
    renderPage();

    const select = (await screen.findByLabelText("Okres:")) as HTMLSelectElement;
    await waitFor(() => {
      const currentOption = Array.from(select.options).find(
        (o) => o.value === "current"
      );
      expect(currentOption?.disabled).toBe(true);
    });
  });
});
