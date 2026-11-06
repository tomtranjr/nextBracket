// The unofficial-tool disclaimer, in one place so the site and the tests share the same copy.

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

/**
 * An ISO date ("2026-03-01") as the charts print it ("1 Mar 26"). Read from the string, not
 * through `Date`, so the time zone can never shift the day. Anything else is returned as given.
 */
export function formatChartDate(iso: string): string {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso);
  const month = match === null ? undefined : MONTHS[Number(match[2]) - 1];
  if (match === null || month === undefined) {
    return iso;
  }
  return `${Number(match[3])} ${month} ${match[1].slice(2)}`;
}

/**
 * The line under a score or a plan. The chart name and date come from the API response, so the
 * line always names the standards version that produced the numbers on screen.
 */
export function shortDisclaimer(chartName: string, effectiveDate: string): string {
  return (
    `Estimate only, based on the ${chartName} effective ${formatChartDate(effectiveDate)}. ` +
    "Check against the official charts and confirm with your UFPM."
  );
}

/**
 * The footer text. It is static, so it names the current charts by hand: update it, and the
 * README copy, when a new chart version ships.
 */
export const FULL_DISCLAIMER =
  "Next Bracket is an independent tool and is not affiliated with or endorsed by the " +
  "Department of the Air Force or the Department of Defense. Scores and plans are estimates " +
  "based on the USAF PFRA Scoring Charts (effective 1 Mar 26) and DAFMAN 36-2905, and may " +
  "contain errors. Always verify your results against the official charts, and contact your " +
  "Unit Fitness Program Manager (UFPM) or Fitness Assessment Cell for official scores and " +
  "policy guidance.";
