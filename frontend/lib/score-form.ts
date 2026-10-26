// Pure helpers for the calculator form: read what a person typed, build the /score request.
// No React here, so Vitest can test all of it.

import { COMPONENTS, type EventKind } from "./events";
import type { ScoreRequest, Sex } from "./types";

// Same limits as `Profile.age` in backend/app/models.py.
export const MIN_AGE = 17;
export const MAX_AGE = 70;

/**
 * Blank text is `empty`, not an error: the person has not typed yet.
 * A time error also lists the bad boxes in `bad`, so the form marks only those.
 */
export type Parsed =
  | { ok: true; value: number }
  | { ok: false; error: string; bad?: TimeBox[] }
  | { empty: true };

const WHOLE = /^\d{1,4}$/;
// "0.52", ".52", "1", "1.0", or more decimals such as "0.5486". The API takes hundredths, so
// `parseRatio` keeps the first two decimals and drops the rest. DAFMAN 36-2905 para 3.15.4.2
// truncates the ratio, it never rounds it.
const RATIO = /^([0-2])?(?:\.(\d+))?$/;

const fail = (error: string): Parsed => ({ ok: false, error });

export function parseAge(text: string): Parsed {
  const t = text.trim();
  if (t === "") return { empty: true };
  if (!WHOLE.test(t)) return fail("Use a whole number.");
  const age = Number(t);
  if (age < MIN_AGE || age > MAX_AGE) return fail(`Age must be ${MIN_AGE} to ${MAX_AGE}.`);
  return { ok: true, value: age };
}

export function parseReps(text: string): Parsed {
  const t = text.trim();
  if (t === "") return { empty: true };
  if (!WHOLE.test(t)) return fail("Use a whole number, 0 or more.");
  return { ok: true, value: Number(t) };
}

export type TimeBox = "minutes" | "seconds";

const MINUTES = /^\d{1,3}$/;
const SECONDS = /^\d{1,2}$/;

const TIME_ERRORS: Record<string, string> = {
  minutes: "Minutes must be a whole number, 0 to 999.",
  seconds: "Seconds must be a whole number, 0 to 59.",
  "minutes,seconds": "Use whole numbers: minutes 0 to 999, seconds 0 to 59.",
};

/**
 * Return whole seconds for the two time boxes: "15" and "40" give 940.
 * A blank box counts as 0, so "15" and "" give 900, and "" and "45" give 45.
 * Seconds of 60 or more is an error, not a carry: "1" and "75" is more likely a typo than 2:15.
 */
export function parseMinutesSeconds(minutes: string, seconds: string): Parsed {
  const m = minutes.trim();
  const s = seconds.trim();
  if (m === "" && s === "") return { empty: true };
  const bad: TimeBox[] = [];
  if (m !== "" && !MINUTES.test(m)) bad.push("minutes");
  if (s !== "" && (!SECONDS.test(s) || Number(s) > 59)) bad.push("seconds");
  if (bad.length > 0) return { ok: false, error: TIME_ERRORS[bad.join(",")], bad };
  return { ok: true, value: Number(m || "0") * 60 + Number(s || "0") };
}

/** Return hundredths, cut by string so there is no float error: "0.52" gives 52, "0.5486" gives 54. */
export function parseRatio(text: string): Parsed {
  const t = text.trim();
  if (t === "") return { empty: true };
  const match = RATIO.exec(t);
  if (match === null) {
    return fail("Use a ratio such as 0.52.");
  }
  const whole = Number(match[1] ?? "0");
  const hundredths = Number((match[2] ?? "").slice(0, 2).padEnd(2, "0"));
  return { ok: true, value: whole * 100 + hundredths };
}

/** The scored value ("0.54") for a ratio typed with more than two decimals, else null. */
export function truncatedRatioText(text: string): string | null {
  const match = RATIO.exec(text.trim());
  if (match === null || (match[2] ?? "").length <= 2) return null;
  const parsed = parseRatio(text);
  return "value" in parsed ? formatRatio(parsed.value) : null;
}

const INCHES = /^(\d{1,3})?(?:\.(\d{1,2}))?$/;

/** Return hundredths of an inch ("32.5" gives 3250), so the ratio math below stays in integers. */
export function parseInches(text: string): Parsed {
  const t = text.trim();
  if (t === "") return { empty: true };
  const match = INCHES.exec(t);
  const message = "Use inches with up to two decimals, for example 32.5.";
  if (match === null) return fail(message);
  const hundredths = Number(match[1] ?? "0") * 100 + Number((match[2] ?? "").padEnd(2, "0"));
  return hundredths > 0 ? { ok: true, value: hundredths } : fail(message);
}

/** Return the ratio text for hundredths: 49 gives "0.49". */
export function formatRatio(hundredths: number): string {
  return (hundredths / 100).toFixed(2);
}

export interface WhtrFromInches {
  /** Waist divided by height, cut to four decimals. For display only. */
  exact: number;
  /** The ratio in hundredths, as the API takes it. */
  hundredths: number;
}

/**
 * Waist over height, truncated to hundredths (DAFMAN 36-2905 para 3.15.4.2, not rounded):
 * 39.5 / 72 = 0.5486 gives 54, and 32.5 / 66 = 0.4924 gives 49.
 * Both arguments are whole hundredths of an inch (at most 99999), so each quotient is exact
 * enough for `Math.floor`: an exact 0.50 gives 50 and a hair under gives 49.
 */
export function whtrFromInches(waist: number, height: number): WhtrFromInches {
  return {
    // Truncated too, so the note never shows a value rounded up across a hundredth.
    exact: Math.floor((10000 * waist) / height) / 10000,
    hundredths: Math.floor((100 * waist) / height),
  };
}

/** What the person has typed for one component. */
export interface ComponentInput {
  /** An event key from `lib/events.ts`. */
  event: string;
  /** The reps or ratio box. Time events use `minutes` and `seconds` instead. */
  text: string;
  minutes: string;
  seconds: string;
}

/** Blank input for an event. A new event has a different unit, so nothing carries over. */
export function emptyInput(event: string): ComponentInput {
  return { event, text: "", minutes: "", seconds: "" };
}

/**
 * Read one result. With `lowerIsBetter`, 0 is an error: a 0:00 run would otherwise score full
 * points and a 0:00 walk would pass. A 0 plank or 0 reps is a real result, so those keep it.
 */
export function parseResult(kind: EventKind, input: ComponentInput, lowerIsBetter = false): Parsed {
  const parsed = readResult(kind, input);
  if (!lowerIsBetter || !("value" in parsed) || parsed.value > 0) return parsed;
  return kind === "time"
    ? { ok: false, error: "Enter a time above 0:00.", bad: ["minutes", "seconds"] }
    : fail("Enter a value above 0.");
}

function readResult(kind: EventKind, input: ComponentInput): Parsed {
  switch (kind) {
    case "reps":
      return parseReps(input.text);
    case "time":
      return parseMinutesSeconds(input.minutes, input.seconds);
    case "ratio":
      return parseRatio(input.text);
  }
}

/** Body composition takes the ratio, or waist and height. */
export type WhtrMode = "ratio" | "measurements";

export interface FormState {
  age: string;
  /** `null` until the person picks one. There is no default on purpose. */
  sex: Sex | null;
  isAfspecwarEod: boolean;
  /** By component key. In `measurements` mode the ratio text in `body_comp` is ignored. */
  components: Record<string, ComponentInput>;
  whtr: { mode: WhtrMode; waist: string; height: string };
}

export function initialFormState(): FormState {
  return {
    age: "",
    sex: null,
    isAfspecwarEod: false,
    components: Object.fromEntries(
      COMPONENTS.map((c) => [c.key, emptyInput(c.events[0].key)]),
    ),
    // Most people know their waist and height, not their ratio, so ask for those first.
    whtr: { mode: "measurements", waist: "", height: "" },
  };
}

export interface BuiltForm {
  /** `null` until age and sex are valid and at least one result is valid. */
  request: ScoreRequest | null;
  /** By field: "age", "waist", "height", or a component key. Only fields with bad text appear. */
  errors: Record<string, string>;
  /** The ratio computed from waist and height, once both are valid. */
  whtr: WhtrFromInches | null;
}

// Same upper bound as `parseRatio`, which reads 0 to 2.99.
const MAX_RATIO_HUNDREDTHS = 299;

// Read the waist and height fields. Blank fields give no value and no error.
function readMeasurements(
  state: FormState,
  errors: Record<string, string>,
): WhtrFromInches | null {
  const waist = parseInches(state.whtr.waist);
  const height = parseInches(state.whtr.height);
  if ("error" in waist) errors.waist = waist.error;
  if ("error" in height) errors.height = height.error;
  if (!("value" in waist) || !("value" in height)) return null;
  const whtr = whtrFromInches(waist.value, height.value);
  if (whtr.hundredths > MAX_RATIO_HUNDREDTHS) {
    errors.waist = "Waist divided by height is 3 or more. Check both numbers.";
    return null;
  }
  // The API rejects a ratio of 0 (lower is better, so 0 is a typo).
  if (whtr.hundredths === 0) {
    errors.waist = "Waist divided by height is under 0.01. Check both numbers.";
    return null;
  }
  return whtr;
}

export function buildScoreRequest(state: FormState): BuiltForm {
  const errors: Record<string, string> = {};

  const age = parseAge(state.age);
  if ("error" in age) errors.age = age.error;

  const values: Record<string, number> = {};
  let whtr: WhtrFromInches | null = null;
  for (const component of COMPONENTS) {
    const input = state.components[component.key];
    const event = component.events.find((e) => e.key === input.event);
    if (event === undefined) continue;
    if (event.kind === "ratio" && state.whtr.mode === "measurements") {
      whtr = readMeasurements(state, errors);
      if (whtr !== null) values[event.key] = whtr.hundredths;
      continue;
    }
    const parsed = parseResult(event.kind, input, event.lowerIsBetter === true);
    if ("error" in parsed) errors[component.key] = parsed.error;
    else if ("value" in parsed) values[event.key] = parsed.value;
  }

  // Narrowing on `age` and `sex` here also gives the request below its types.
  if (!("value" in age) || state.sex === null || Object.keys(values).length === 0) {
    return { request: null, errors, whtr };
  }

  return {
    request: {
      profile: { age: age.value, sex: state.sex, is_afspecwar_eod: state.isAfspecwarEod },
      results: { values },
    },
    errors,
    whtr,
  };
}
