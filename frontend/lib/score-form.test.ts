import { describe, expect, it } from "vitest";

import {
  buildScoreRequest,
  initialFormState,
  parseAge,
  parseRatio,
  parseReps,
  parseResult,
  parseTimeText,
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

describe("parseTimeText", () => {
  it("reads m:ss as seconds", () => {
    expect(parseTimeText("15:40")).toEqual(ok(940));
  });

  it("treats blank as empty", () => {
    expect(parseTimeText("")).toEqual({ empty: true });
  });

  it.each(["15:7", "15", "15:60", "abc"])("rejects %s", (text) => {
    expect(parseTimeText(text)).toMatchObject({ ok: false, error: "Use m:ss, for example 15:40." });
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
  ])("reads %s as %i hundredths", (text, hundredths) => {
    expect(parseRatio(text)).toEqual(ok(hundredths));
  });

  it("treats blank as empty", () => {
    expect(parseRatio("")).toEqual({ empty: true });
  });

  // More than two decimals is an error and is never rounded.
  it.each(["0.525", "0.5.2", "-0.5", "3", "0,52", ".", "1.", "abc"])("rejects %s", (text) => {
    expect(parseRatio(text)).toMatchObject({ ok: false });
  });
});

describe("parseResult", () => {
  it("picks the parser from the event kind", () => {
    expect(parseResult("reps", "30")).toEqual(ok(30));
    expect(parseResult("time", "1:30")).toEqual(ok(90));
    expect(parseResult("ratio", "0.50")).toEqual(ok(50));
  });
});

function filled(change: (state: FormState) => void): FormState {
  const state = initialFormState();
  state.age = "27";
  state.sex = "M";
  state.components.cardio.text = "15:40";
  change(state);
  return state;
}

describe("buildScoreRequest", () => {
  it("starts with no request and no errors", () => {
    expect(buildScoreRequest(initialFormState())).toEqual({ request: null, errors: {} });
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
    expect(buildScoreRequest(filled((s) => (s.components.cardio.text = ""))).request).toBeNull();
  });

  it("builds a request from partial results", () => {
    expect(buildScoreRequest(filled(() => {}))).toEqual({
      request: {
        profile: { age: 27, sex: "M", is_afspecwar_eod: false },
        results: { values: { run_2mile: 940 } },
      },
      errors: {},
    });
  });

  it("uses the chosen event of each component", () => {
    const built = buildScoreRequest(
      filled((s) => {
        s.components.cardio = { event: "hamr_20m", text: "60" };
        s.components.core = { event: "forearm_plank", text: "2:00" };
        s.components.body_comp.text = "0.49";
      }),
    );
    expect(built.request?.results.values).toEqual({ hamr_20m: 60, forearm_plank: 120, whtr: 49 });
  });

  it("passes the AFSPECWAR/EOD flag through", () => {
    const built = buildScoreRequest(filled((s) => (s.isAfspecwarEod = true)));
    expect(built.request?.profile.is_afspecwar_eod).toBe(true);
  });

  it("drops a bad field, reports it, and still scores the rest", () => {
    const built = buildScoreRequest(
      filled((s) => {
        s.components.strength.text = "-3";
        s.components.body_comp.text = "0.525";
      }),
    );
    expect(built.request?.results.values).toEqual({ run_2mile: 940 });
    expect(Object.keys(built.errors).sort()).toEqual(["body_comp", "strength"]);
  });

  it("sends nothing when the only result is bad", () => {
    const built = buildScoreRequest(filled((s) => (s.components.cardio.text = "15:7")));
    expect(built.request).toBeNull();
    expect(built.errors.cardio).toBeDefined();
  });
});
