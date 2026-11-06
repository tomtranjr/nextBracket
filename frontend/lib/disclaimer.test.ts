import { describe, expect, it } from "vitest";

import { formatChartDate, FULL_DISCLAIMER, shortDisclaimer } from "@/lib/disclaimer";

describe("formatChartDate", () => {
  it("prints the date the way the charts do", () => {
    expect(formatChartDate("2026-03-01")).toBe("1 Mar 26");
    expect(formatChartDate("2027-12-15")).toBe("15 Dec 27");
  });

  it("returns anything that is not an ISO date unchanged", () => {
    expect(formatChartDate("soon")).toBe("soon");
    expect(formatChartDate("2026-13-01")).toBe("2026-13-01");
  });
});

describe("shortDisclaimer", () => {
  it("names the charts and date it is given", () => {
    expect(shortDisclaimer("USAF PFRA Scoring Charts", "2026-03-01")).toBe(
      "Estimate only, based on the USAF PFRA Scoring Charts effective 1 Mar 26. " +
        "Check against the official charts and confirm with your UFPM.",
    );
    expect(shortDisclaimer("Next Charts", "2027-10-01")).toContain(
      "Next Charts effective 1 Oct 27",
    );
  });
});

describe("FULL_DISCLAIMER", () => {
  it("says the tool is unofficial and points to the UFPM", () => {
    expect(FULL_DISCLAIMER).toContain("not affiliated with or endorsed by");
    expect(FULL_DISCLAIMER).toContain("USAF PFRA Scoring Charts (effective 1 Mar 26)");
    expect(FULL_DISCLAIMER).toContain("DAFMAN 36-2905");
    expect(FULL_DISCLAIMER).toContain("Unit Fitness Program Manager (UFPM)");
  });
});
