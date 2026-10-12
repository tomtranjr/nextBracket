import { describe, expect, it } from "vitest";

import { formatTime, parseTime } from "@/lib/time";

describe("parseTime", () => {
  it.each([
    ["15:40", 940],
    ["0:00", 0],
    ["0:59", 59],
    ["1:00", 60],
    ["9:05", 545],
    [" 15:40 ", 940],
  ])("reads %j as %i seconds", (text, seconds) => {
    expect(parseTime(text)).toBe(seconds);
  });

  it.each(["", "15", "15:5", "15:60", "-1:30", "1:2:3", "15:40.5", "ab:cd", "15:40\n15:40"])(
    "rejects %j",
    (text) => {
      expect(() => parseTime(text)).toThrow("m:ss");
    },
  );
});

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

  it("round-trips every whole second up to an hour", () => {
    for (let s = 0; s < 3600; s++) {
      expect(parseTime(formatTime(s))).toBe(s);
    }
  });
});
