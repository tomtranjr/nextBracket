import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { PlanAnswer } from "@/components/Planner";
import { ScoreResult } from "@/components/ScoreResult";
import { Disclaimer, SiteFooter } from "@/components/Disclaimer";
import { FULL_DISCLAIMER } from "@/lib/disclaimer";
import type { PlanResult, ScoreReport } from "@/lib/types";

// Static markup is enough here: these check what text is on screen, not how it behaves.
// React escapes text, so compare against the same escaping.
const html = (text: string) => renderToStaticMarkup(<>{text}</>);

const SHORT =
  "Estimate only, based on the Test Charts effective 1 Mar 26. " +
  "Check against the official charts and confirm with your UFPM.";

const report: ScoreReport = {
  version: "test",
  effective_date: "2026-03-01",
  chart_name: "Test Charts",
  components: [
    {
      component: "strength",
      event: "push_up",
      result: 45,
      points: 8.5,
      max_points: 15,
      minimum_met: true,
      minimum: 28,
      minimum_gap: null,
      full_points_at: 63,
      full_points_gap: 18,
    },
  ],
  not_scored: ["cardio", "core", "body_comp"],
  total: null,
  category: null,
  missed_minimums: [],
  points_possible: 100,
  points_earned: null,
  walk: null,
  assumptions: [],
};

const plan: PlanResult = {
  version: "test",
  effective_date: "2026-03-01",
  chart_name: "Test Charts",
  target: 90,
  status: "already_met",
  current_total: 92,
  max_total: 100,
  assumed_components: [],
  options: [],
};

const noop = () => {};

describe("SiteFooter", () => {
  it("shows the full disclaimer in a footer", () => {
    const markup = renderToStaticMarkup(<SiteFooter />);
    expect(markup).toMatch(/^<footer/);
    expect(markup).toContain(html(FULL_DISCLAIMER));
  });
});

describe("Disclaimer", () => {
  it("short variant names the charts it is given", () => {
    const markup = renderToStaticMarkup(
      <Disclaimer variant="short" chartName="Test Charts" effectiveDate="2026-03-01" />,
    );
    expect(markup).toContain(html(SHORT));
  });
});

describe("ScoreResult", () => {
  it("shows the short line, from the report, with a score", () => {
    const markup = renderToStaticMarkup(
      <ScoreResult report={report} error={null} pending={false} onRetry={noop} />,
    );
    expect(markup).toContain(html(SHORT));
    // Inside the polite live region, so it opts out of announcements itself.
    expect(markup).toMatch(/<div aria-live="off"><p[^>]*>Estimate only/);
  });

  it("has no short line before there is a score", () => {
    const markup = renderToStaticMarkup(
      <ScoreResult report={null} error={null} pending={false} onRetry={noop} />,
    );
    expect(markup).not.toContain("Estimate only");
  });
});

describe("PlanAnswer", () => {
  it("shows the short line, from the plan, outside the live region", () => {
    const markup = renderToStaticMarkup(
      <PlanAnswer hint={null} error={null} result={plan} pending={false} onRetry={noop} />,
    );
    // The live region is the first element. The line comes after it closes, as its sibling.
    expect(markup).toMatch(/^<div aria-live="polite"/);
    expect(
      markup.endsWith(
        `</div><p class="text-sm text-zinc-600 dark:text-zinc-400">${html(SHORT)}</p>`,
      ),
    ).toBe(true);
    expect(markup.match(/Estimate only/g)).toHaveLength(1);
  });

  it("has no short line while a hint replaces the plan", () => {
    const markup = renderToStaticMarkup(
      <PlanAnswer
        hint="Enter a target."
        error={null}
        result={plan}
        pending={false}
        onRetry={noop}
      />,
    );
    expect(markup).not.toContain("Estimate only");
  });
});
