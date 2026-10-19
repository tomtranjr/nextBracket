import { describe, expect, it } from "vitest";

import { formatPoints, formatResult, minimumNote, pointsNote } from "@/lib/format";

describe("formatPoints", () => {
  it("shows whole numbers with no decimal", () => {
    expect(formatPoints(90)).toBe("90");
    expect(formatPoints(0)).toBe("0");
  });

  it("shows one decimal for a half", () => {
    expect(formatPoints(87.5)).toBe("87.5");
    expect(formatPoints(2.5)).toBe("2.5");
  });
});

describe("formatResult", () => {
  it("shows seconds as m:ss", () => {
    expect(formatResult("time", 940)).toBe("15:40");
    expect(formatResult("time", 65)).toBe("1:05");
  });

  it("shows hundredths as a ratio", () => {
    expect(formatResult("ratio", 49)).toBe("0.49");
    expect(formatResult("ratio", 100)).toBe("1.00");
  });

  it("shows reps as a plain number", () => {
    expect(formatResult("reps", 45)).toBe("45");
  });
});

describe("minimumNote", () => {
  it("shows the minimum when it is met", () => {
    const scored = { minimum_met: true, minimum: 1195, minimum_gap: null };
    expect(minimumNote("time", scored)).toEqual({ met: true, text: "Minimum 19:55 met" });
  });

  it("shows the gap in m:ss for a time", () => {
    const scored = { minimum_met: false, minimum: 1195, minimum_gap: 20 };
    expect(minimumNote("time", scored)).toEqual({
      met: false,
      text: "Minimum 19:55 missed by 0:20",
    });
  });

  it("shows the gap in reps", () => {
    const scored = { minimum_met: false, minimum: 28, minimum_gap: 3 };
    expect(minimumNote("reps", scored)).toEqual({ met: false, text: "Minimum 28 missed by 3" });
  });

  it("returns null when there is no minimum", () => {
    const scored = { minimum_met: null, minimum: null, minimum_gap: null };
    expect(minimumNote("ratio", scored)).toBeNull();
  });
});

describe("pointsNote", () => {
  it("says full points when there is no gap", () => {
    const scored = { points: 20, full_points_at: 49, full_points_gap: null };
    expect(pointsNote("ratio", scored)).toEqual({ tone: "full", text: "Full points" });
  });

  it("is partial with some points, and shows the top row and the gap", () => {
    const scored = { points: 17, full_points_at: 49, full_points_gap: 3 };
    expect(pointsNote("ratio", scored)).toEqual({
      tone: "partial",
      text: "Full points at 0.49, 0.03 over",
    });
  });

  it("is none with zero points", () => {
    const scored = { points: 0, full_points_at: 49, full_points_gap: 13 };
    expect(pointsNote("ratio", scored)).toEqual({
      tone: "none",
      text: "Full points at 0.49, 0.13 over",
    });
  });

  it("formats a time in m:ss", () => {
    const scored = { points: 30, full_points_at: 780, full_points_gap: 20 };
    expect(pointsNote("time", scored).text).toBe("Full points at 13:00, 0:20 over");
  });
});
