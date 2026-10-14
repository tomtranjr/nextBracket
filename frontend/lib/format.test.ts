import { describe, expect, it } from "vitest";

import { formatPoints, formatResult } from "@/lib/format";

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
