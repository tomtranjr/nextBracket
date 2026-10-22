import { describe, expect, it } from "vitest";

import { formatTime } from "@/lib/time";

describe("formatTime", () => {
  it.each([
    [940, "15:40"],
    [0, "0:00"],
    [545, "9:05"],
  ])("writes %i seconds as %j", (seconds, text) => {
    expect(formatTime(seconds)).toBe(text);
  });

  it.each([-1, 1.5, Number.NaN])("rejects %d", (seconds) => {
    expect(() => formatTime(seconds)).toThrow("whole number");
  });
});
