import { describe, expect, it } from "vitest";

import {
  assumptionNote,
  buildPlanRequest,
  formatChange,
  groupOptions,
  parseTarget,
  planHint,
  statusText,
  TARGET_PRESETS,
} from "@/lib/plan-form";
import {
  buildScoreRequest,
  initialFormState,
  type FormState,
  type Parsed,
} from "@/lib/score-form";
import type { EventChange, PlanOption, PlanResult } from "@/lib/types";

const ok = (value: number): Parsed => ({ ok: true, value });

describe("parseTarget", () => {
  it("accepts whole numbers and halves from 0 to 100", () => {
    expect(parseTarget("0")).toEqual(ok(0));
    expect(parseTarget("90")).toEqual(ok(90));
    expect(parseTarget(" 87.5 ")).toEqual(ok(87.5));
    expect(parseTarget("87.50")).toEqual(ok(87.5));
    expect(parseTarget("90.0")).toEqual(ok(90));
    expect(parseTarget("100")).toEqual(ok(100));
    expect(parseTarget(".5")).toEqual(ok(0.5));
  });

  it("treats blank as empty", () => {
    expect(parseTarget("")).toEqual({ empty: true });
    expect(parseTarget("  ")).toEqual({ empty: true });
  });

  it.each(["90.3", "90.25", "90.", ".", "abc", "-5", "1e2", "9 0"])("rejects %s", (text) => {
    expect(parseTarget(text)).toMatchObject({ ok: false });
  });

  it("rejects a target above 100", () => {
    expect(parseTarget("101")).toEqual({ ok: false, error: "Target must be 0 to 100." });
    expect(parseTarget("100.5")).toMatchObject({ ok: false });
  });

  it("has presets that parse", () => {
    for (const preset of TARGET_PRESETS) {
      expect(parseTarget(String(preset.value))).toEqual(ok(preset.value));
    }
  });
});

// A form with age, sex, and the results given by event key.
function formWith(texts: Partial<Record<string, string>>, ready = true): FormState {
  const state = initialFormState();
  if (ready) {
    state.age = "27";
    state.sex = "M";
  }
  if (texts.run !== undefined) state.components.cardio.text = texts.run;
  if (texts.pushUp !== undefined) state.components.strength.text = texts.pushUp;
  return state;
}

describe("buildPlanRequest", () => {
  it("builds a request from the score request and a target", () => {
    const built = buildScoreRequest(formWith({ run: "15:40", pushUp: "45" }));
    expect(buildPlanRequest(built, ok(90))).toEqual({
      profile: { age: 27, sex: "M", is_afspecwar_eod: false },
      target: 90,
      current: { values: { run_2mile: 940, push_up: 45 } },
    });
  });

  it("passes the AFSPECWAR/EOD flag", () => {
    const state = formWith({ run: "15:40" });
    state.isAfspecwarEod = true;
    const request = buildPlanRequest(buildScoreRequest(state), ok(75));
    expect(request?.profile.is_afspecwar_eod).toBe(true);
  });

  it("returns null with no valid score request", () => {
    const built = buildScoreRequest(formWith({}));
    expect(buildPlanRequest(built, ok(90))).toBeNull();
  });

  it.each([{ empty: true } as const, { ok: false, error: "bad" } as const])(
    "returns null with target %j",
    (target) => {
      const built = buildScoreRequest(formWith({ run: "15:40" }));
      expect(buildPlanRequest(built, target)).toBeNull();
    },
  );
});

describe("planHint", () => {
  const hint = (state: FormState, target = parseTarget("")) =>
    planHint(state, buildScoreRequest(state), target);

  it("asks for age and sex first", () => {
    expect(hint(formWith({ run: "15:40" }, false))).toBe("Enter your age and sex.");
    const noSex = formWith({ run: "15:40" });
    noSex.sex = null;
    expect(hint(noSex)).toBe("Enter your age and sex.");
  });

  it("asks for a result next", () => {
    expect(hint(formWith({}))).toBe("Enter at least one result.");
  });

  it("asks for a target last", () => {
    expect(hint(formWith({ run: "15:40" }))).toBe("Enter a target.");
  });

  it("is null when the plan can run, or when the target field shows its own error", () => {
    const state = formWith({ run: "15:40" });
    expect(hint(state, parseTarget("90"))).toBeNull();
    expect(hint(state, parseTarget("90.3"))).toBeNull();
  });
});

describe("assumptionNote", () => {
  it("is null when nothing is assumed", () => {
    expect(assumptionNote([])).toBeNull();
  });

  it("names the components", () => {
    expect(assumptionNote(["strength", "core"])).toBe(
      "No result for strength, core. It starts from the minimum for each.",
    );
    expect(assumptionNote(["core"])).toBe("No result for core. It starts from the minimum.");
  });

  it("says body composition starts at 0 points", () => {
    expect(assumptionNote(["body_comp"])).toBe(
      "No result for body composition. It starts from the minimum. " +
        "Body composition starts at 0 points.",
    );
  });
});

function plan(overrides: Partial<PlanResult>): PlanResult {
  return {
    version: "2026-03-01",
    effective_date: "2026-03-01",
    target: 90,
    status: "options",
    current_total: 84.5,
    max_total: 100,
    assumed_components: [],
    options: [],
    ...overrides,
  };
}

describe("statusText", () => {
  it("is null when there are options", () => {
    expect(statusText(plan({ status: "options" }))).toBeNull();
  });

  it("says a met target is met when nothing is assumed", () => {
    expect(statusText(plan({ status: "already_met", target: 75 }))).toBe(
      "You already reach 75.",
    );
  });

  it("does not claim a result when components are assumed", () => {
    // Real case: only WHtR entered, target 60. The assumed minimums alone total 60.
    const text = statusText(
      plan({
        status: "already_met",
        target: 60,
        current_total: 60,
        assumed_components: ["cardio", "strength", "core"],
      }),
    );
    expect(text).toBe(
      "At the minimums assumed for cardio, strength, core, you already reach 60. " +
        "Enter your real results for a true answer.",
    );
  });

  it("gives the best total for an impossible target", () => {
    expect(statusText(plan({ status: "impossible", target: 99.5, max_total: 97.5 }))).toBe(
      "Your target of 99.5 is above the best total possible for your profile: 97.5.",
    );
  });
});

const option = (kind: PlanOption["kind"], projected_total = 90): PlanOption => ({
  kind,
  changes: [],
  projected_total,
});

describe("groupOptions", () => {
  it("orders groups single event, balanced, quick wins", () => {
    const groups = groupOptions([option("quick_wins"), option("balanced"), option("single_event")]);
    expect(groups.map((g) => g.kind)).toEqual(["single_event", "balanced", "quick_wins"]);
  });

  it("keeps backend order inside a group and drops empty groups", () => {
    const first = option("single_event", 90);
    const second = option("single_event", 91);
    const groups = groupOptions([first, second]);
    expect(groups).toHaveLength(1);
    expect(groups[0].options).toEqual([first, second]);
  });

  it("returns no groups for no options", () => {
    expect(groupOptions([])).toEqual([]);
  });

  it("never calls a group the easiest", () => {
    const groups = groupOptions([option("single_event"), option("balanced"), option("quick_wins")]);
    for (const group of groups) {
      expect(`${group.heading} ${group.text}`.toLowerCase()).not.toContain("easiest");
    }
  });
});

const change = (overrides: Partial<EventChange>): EventChange => ({
  component: "cardio",
  event: "run_2mile",
  unit: "seconds",
  from_result: 940,
  to_result: 853,
  delta: -87,
  from_points: 44,
  to_points: 47.5,
  ...overrides,
});

describe("formatChange", () => {
  it("formats a time with the event label and points", () => {
    expect(formatChange(change({}))).toBe("2-mile run: 15:40 to 14:13 (44 to 47.5 points)");
  });

  it("formats reps", () => {
    expect(
      formatChange(
        change({
          component: "strength",
          event: "push_up",
          unit: "reps",
          from_result: 45,
          to_result: 60,
          from_points: 12,
          to_points: 15,
        }),
      ),
    ).toBe("Push-up: 45 to 60 (12 to 15 points)");
  });

  it("formats a ratio from hundredths", () => {
    expect(
      formatChange(
        change({
          component: "body_comp",
          event: "whtr",
          unit: "hundredths",
          from_result: 52,
          to_result: 49,
          from_points: 15,
          to_points: 20,
        }),
      ),
    ).toBe("Waist-to-height ratio: 0.52 to 0.49 (15 to 20 points)");
  });

  it("says when the starting result was assumed", () => {
    expect(
      formatChange(
        change({
          component: "strength",
          event: "push_up",
          unit: "reps",
          from_result: null,
          to_result: 63,
          delta: null,
          from_points: 2.5,
          to_points: 15,
        }),
      ),
    ).toBe("Push-up: no result (assumed at the minimum) to 63 (2.5 to 15 points)");
  });

  it("falls back to the raw key for an unknown event", () => {
    expect(formatChange(change({ event: "new_event", from_result: 1, to_result: 2 }))).toBe(
      "new_event: 1 to 2 (44 to 47.5 points)",
    );
  });
});
