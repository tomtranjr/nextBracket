import { describe, expect, it } from "vitest";

import {
  buildScoreRequest,
  emptyInput,
  initialFormState,
  formatRatio,
  parseAge,
  parseInches,
  parseRatio,
  truncatedRatioText,
  parseReps,
  parseResult,
  parseMinutesSeconds,
  whtrFromInches,
  type FormState,
} from "@/lib/score-form";

const ok = (value: number) => ({ ok: true, value });

describe("parseAge", () => {
  it("accepts the limits", () => {
    expect(parseAge("17")).toEqual(ok(17));
    expect(parseAge(" 70 ")).toEqual(ok(70));
  });

  it("treats blank as empty", () => {
    expect(parseAge("")).toEqual({ empty: true });
    expect(parseAge("  ")).toEqual({ empty: true });
  });

  it.each(["16", "71", "27.5", "-3", "abc", "1e1"])("rejects %s", (text) => {
    expect(parseAge(text)).toMatchObject({ ok: false });
  });
});

describe("parseReps", () => {
  it("accepts whole numbers from 0", () => {
    expect(parseReps("0")).toEqual(ok(0));
    expect(parseReps("45")).toEqual(ok(45));
  });

  it.each(["-3", "4.5", "x", "1e2"])("rejects %s", (text) => {
    expect(parseReps(text)).toMatchObject({ ok: false });
  });
});

describe("parseMinutesSeconds", () => {
  it.each([
    ["15", "40", 940],
    ["0", "0", 0],
    ["999", "59", 59999],
    ["1", "5", 65],
    ["1", "05", 65],
    [" 15 ", " 40 ", 940],
  ])("reads %j and %j as %i seconds", (minutes, seconds, total) => {
    expect(parseMinutesSeconds(minutes, seconds)).toEqual(ok(total));
  });

  it("treats both boxes blank as empty", () => {
    expect(parseMinutesSeconds("", "")).toEqual({ empty: true });
    expect(parseMinutesSeconds(" ", " ")).toEqual({ empty: true });
  });

  it("counts one blank box as 0", () => {
    expect(parseMinutesSeconds("15", "")).toEqual(ok(900));
    expect(parseMinutesSeconds("", "45")).toEqual(ok(45));
  });

  it.each(["abc", "1.5", "-1", "1000", "15:40"])("rejects minutes %j", (minutes) => {
    expect(parseMinutesSeconds(minutes, "40")).toEqual({
      ok: false,
      error: "Minutes must be a whole number, 0 to 999.",
      bad: ["minutes"],
    });
  });

  // No carry: 60 or more is a typo to fix, not extra minutes.
  it.each(["60", "75", "99", "100", "abc", "4.5", "-1"])("rejects seconds %j", (seconds) => {
    expect(parseMinutesSeconds("15", seconds)).toEqual({
      ok: false,
      error: "Seconds must be a whole number, 0 to 59.",
      bad: ["seconds"],
    });
  });

  it("marks both boxes when both are bad", () => {
    expect(parseMinutesSeconds("x", "75")).toEqual({
      ok: false,
      error: "Use whole numbers: minutes 0 to 999, seconds 0 to 59.",
      bad: ["minutes", "seconds"],
    });
  });
});

describe("parseRatio", () => {
  it.each([
    ["0.52", 52],
    [".52", 52],
    ["0.5", 50],
    ["0.05", 5],
    ["0.49", 49],
    ["1", 100],
    ["1.0", 100],
    ["0", 0],
    // More than two decimals are cut, never rounded (DAFMAN 36-2905 para 3.15.4.2).
    ["0.525", 52],
    ["0.5486", 54],
    ["0.4999", 49],
    ["2.999", 299],
  ])("reads %s as %i hundredths", (text, hundredths) => {
    expect(parseRatio(text)).toEqual(ok(hundredths));
  });

  it("treats blank as empty", () => {
    expect(parseRatio("")).toEqual({ empty: true });
  });

  it.each(["0.5.2", "-0.5", "3", "0,52", ".", "1.", "abc"])("rejects %s", (text) => {
    expect(parseRatio(text)).toMatchObject({ ok: false });
  });
});

describe("parseInches", () => {
  it.each([
    ["32", 3200],
    ["32.5", 3250],
    ["32.25", 3225],
    [".5", 50],
    [" 66 ", 6600],
  ])("reads %s as %i hundredths of an inch", (text, hundredths) => {
    expect(parseInches(text)).toEqual(ok(hundredths));
  });

  it("treats blank as empty", () => {
    expect(parseInches("")).toEqual({ empty: true });
  });

  it.each(["0", "0.00", "-3", "32.255", "abc", "32.", "1234", "32,5"])("rejects %s", (text) => {
    expect(parseInches(text)).toMatchObject({ ok: false });
  });
});

describe("whtrFromInches", () => {
  it.each([
    ["32.5 / 66 = 0.4924", 3250, 6600, 49],
    ["33 / 66 = 0.50", 3300, 6600, 50],
    ["DAFMAN example: 39.5 / 72 = 0.5486, truncated", 3950, 7200, 54],
    ["99 / 200 is exactly 0.495, truncated", 9900, 20000, 49],
    ["49.49 / 100 = 0.4949", 4949, 10000, 49],
    ["49.5 / 100 is exactly 0.495, truncated", 4950, 10000, 49],
    ["exactly 0.50 stays 50", 3300, 6600, 50],
    ["a hair under 0.50 is 49", 3299, 6600, 49],
    ["equal waist and height", 6600, 6600, 100],
  ])("%s", (_name, waist, height, hundredths) => {
    expect(whtrFromInches(waist, height).hundredths).toBe(hundredths);
  });

  it("returns the ratio cut to four decimals for display", () => {
    expect(whtrFromInches(3250, 6600).exact).toBeCloseTo(0.4924, 4);
    expect(whtrFromInches(3950, 7200).exact).toBe(0.5486);
  });

  it("never shows a value rounded up across a hundredth", () => {
    // 49995 / 99999 = 0.499955: toFixed(4) of the raw ratio gives 0.5000, but it scores 49.
    const result = whtrFromInches(49995, 99999);
    expect(result.hundredths).toBe(49);
    expect(result.exact.toFixed(4)).toBe("0.4999");
  });
});

describe("formatRatio", () => {
  it.each([
    [49, "0.49"],
    [50, "0.50"],
    [5, "0.05"],
    [100, "1.00"],
  ])("formats %i as %s", (hundredths, text) => {
    expect(formatRatio(hundredths)).toBe(text);
  });
});

describe("parseResult", () => {
  it("picks the parser from the event kind", () => {
    const input = { event: "any", text: "30", minutes: "1", seconds: "30" };
    expect(parseResult("reps", input)).toEqual(ok(30));
    expect(parseResult("time", input)).toEqual(ok(90));
    expect(parseResult("ratio", { ...input, text: "0.50" })).toEqual(ok(50));
  });
});

function filled(change: (state: FormState) => void): FormState {
  const state = initialFormState();
  state.age = "27";
  state.sex = "M";
  state.components.cardio.minutes = "15";
  state.components.cardio.seconds = "40";
  change(state);
  return state;
}

describe("buildScoreRequest", () => {
  it("starts with no request and no errors", () => {
    expect(buildScoreRequest(initialFormState())).toEqual({ request: null, errors: {}, whtr: null });
  });

  it("sends nothing until sex is picked", () => {
    expect(buildScoreRequest(filled((s) => (s.sex = null))).request).toBeNull();
  });

  it("sends nothing until age is valid", () => {
    expect(buildScoreRequest(filled((s) => (s.age = ""))).request).toBeNull();
    const built = buildScoreRequest(filled((s) => (s.age = "12")));
    expect(built.request).toBeNull();
    expect(built.errors.age).toBeDefined();
  });

  it("sends nothing until one result is valid", () => {
    expect(
      buildScoreRequest(filled((s) => (s.components.cardio = emptyInput("run_2mile")))).request,
    ).toBeNull();
  });

  it("builds a request from partial results", () => {
    expect(buildScoreRequest(filled(() => {}))).toEqual({
      request: {
        profile: { age: 27, sex: "M", is_afspecwar_eod: false },
        results: { values: { run_2mile: 940 } },
      },
      errors: {},
      whtr: null,
    });
  });

  it("uses the chosen event of each component", () => {
    const built = buildScoreRequest(
      filled((s) => {
        s.components.cardio = { ...emptyInput("hamr_20m"), text: "60" };
        s.components.core = { ...emptyInput("forearm_plank"), minutes: "2" };
        s.whtr.mode = "ratio";
        s.components.body_comp.text = "0.49";
      }),
    );
    expect(built.request?.results.values).toEqual({ hamr_20m: 60, forearm_plank: 120, whtr: 49 });
  });

  it("asks for waist and height first, and ignores the ratio text until the user picks ratio", () => {
    expect(initialFormState().whtr.mode).toBe("measurements");
    const built = buildScoreRequest(filled((s) => (s.components.body_comp.text = "0.49")));
    expect(built.request?.results.values).toEqual({ run_2mile: 940 });
  });

  it("passes the AFSPECWAR/EOD flag through", () => {
    const built = buildScoreRequest(filled((s) => (s.isAfspecwarEod = true)));
    expect(built.request?.profile.is_afspecwar_eod).toBe(true);
  });

  it("drops a bad field, reports it, and still scores the rest", () => {
    const built = buildScoreRequest(
      filled((s) => {
        s.components.strength.text = "-3";
        s.whtr.mode = "ratio";
        s.components.body_comp.text = "0.5.2";
      }),
    );
    expect(built.request?.results.values).toEqual({ run_2mile: 940 });
    expect(Object.keys(built.errors).sort()).toEqual(["body_comp", "strength"]);
  });

  it("sends nothing when the only result is bad", () => {
    const built = buildScoreRequest(filled((s) => (s.components.cardio.seconds = "75")));
    expect(built.request).toBeNull();
    expect(built.errors.cardio).toBeDefined();
  });
});

describe("buildScoreRequest with waist and height", () => {
  function measured(waist: string, height: string, ratioText = ""): FormState {
    return filled((s) => {
      s.whtr = { mode: "measurements", waist, height };
      s.components.body_comp.text = ratioText;
    });
  }

  it("sends the computed ratio and returns it for display", () => {
    const built = buildScoreRequest(measured("32.5", "66"));
    expect(built.request?.results.values).toEqual({ run_2mile: 940, whtr: 49 });
    expect(built.whtr?.hundredths).toBe(49);
    expect(built.whtr?.exact).toBeCloseTo(0.4924, 4);
  });

  it("truncates, never rounds", () => {
    expect(buildScoreRequest(measured("49.5", "100")).request?.results.values.whtr).toBe(49);
    expect(buildScoreRequest(measured("39.5", "72")).request?.results.values.whtr).toBe(54);
  });

  it("ignores the ratio text in this mode", () => {
    const built = buildScoreRequest(measured("33", "66", "0.30"));
    expect(built.request?.results.values.whtr).toBe(50);
  });

  it("sends no WHtR and no error while one field is blank", () => {
    for (const [waist, height] of [["32.5", ""], ["", "66"], ["", ""]]) {
      const built = buildScoreRequest(measured(waist, height));
      expect(built.request?.results.values).toEqual({ run_2mile: 940 });
      expect(built.errors).toEqual({});
      expect(built.whtr).toBeNull();
    }
  });

  it("reports a bad field and still scores the rest", () => {
    const built = buildScoreRequest(measured("32.5", "abc"));
    expect(built.errors.height).toBeDefined();
    expect(built.errors.waist).toBeUndefined();
    expect(built.request?.results.values).toEqual({ run_2mile: 940 });
  });

  it("rejects a ratio of 3 or more", () => {
    const built = buildScoreRequest(measured("200", "66"));
    expect(built.errors.waist).toBeDefined();
    expect(built.request?.results.values).toEqual({ run_2mile: 940 });
  });

  it("ignores waist and height in ratio mode", () => {
    const built = buildScoreRequest(
      filled((s) => {
        s.whtr = { mode: "ratio", waist: "33", height: "66" };
        s.components.body_comp.text = "0.40";
      }),
    );
    expect(built.request?.results.values.whtr).toBe(40);
    expect(built.whtr).toBeNull();
  });
});

describe("truncatedRatioText", () => {
  it("gives the scored value when digits are dropped", () => {
    expect(truncatedRatioText("0.5486")).toBe("0.54");
    expect(truncatedRatioText(" 0.525 ")).toBe("0.52");
  });

  it("gives null when nothing is dropped, or the text is not a ratio", () => {
    expect(truncatedRatioText("0.52")).toBeNull();
    expect(truncatedRatioText("0.5")).toBeNull();
    expect(truncatedRatioText("")).toBeNull();
    expect(truncatedRatioText("abc")).toBeNull();
  });
});
