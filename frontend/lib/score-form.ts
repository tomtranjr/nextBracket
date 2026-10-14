// Pure helpers for the calculator form: read what a person typed, build the /score request.
// No React here, so Vitest can test all of it.

import { COMPONENTS, type EventKind } from "./events";
import type { ScoreRequest, Sex } from "./types";
import { parseTime } from "./time";

// Same limits as `Profile.age` in backend/app/models.py.
export const MIN_AGE = 17;
export const MAX_AGE = 70;

/** Blank text is `empty`, not an error: the person has not typed yet. */
export type Parsed = { ok: true; value: number } | { ok: false; error: string } | { empty: true };

const WHOLE = /^\d{1,4}$/;
// "0.52", ".52", "1", "1.0". Two decimals at most, because the API takes hundredths and we do
// not round: 0.525 has no rule in the charts, so the person must pick a value.
const RATIO = /^([0-2])?(?:\.(\d{1,2}))?$/;

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

export function parseTimeText(text: string): Parsed {
  if (text.trim() === "") return { empty: true };
  try {
    return { ok: true, value: parseTime(text) };
  } catch {
    return fail("Use m:ss, for example 15:40.");
  }
}

/** Return hundredths: "0.52" gives 52. */
export function parseRatio(text: string): Parsed {
  const t = text.trim();
  if (t === "") return { empty: true };
  const match = RATIO.exec(t);
  if (match === null) {
    return fail("Use a ratio with two decimals, for example 0.52.");
  }
  const whole = Number(match[1] ?? "0");
  const hundredths = Number((match[2] ?? "").padEnd(2, "0"));
  return { ok: true, value: whole * 100 + hundredths };
}

export function parseResult(kind: EventKind, text: string): Parsed {
  switch (kind) {
    case "reps":
      return parseReps(text);
    case "time":
      return parseTimeText(text);
    case "ratio":
      return parseRatio(text);
  }
}

/** What the person has typed for one component. */
export interface ComponentInput {
  /** An event key from `lib/events.ts`. */
  event: string;
  text: string;
}

export interface FormState {
  age: string;
  /** `null` until the person picks one. There is no default on purpose. */
  sex: Sex | null;
  isAfspecwarEod: boolean;
  /** By component key. */
  components: Record<string, ComponentInput>;
}

export function initialFormState(): FormState {
  return {
    age: "",
    sex: null,
    isAfspecwarEod: false,
    components: Object.fromEntries(
      COMPONENTS.map((c) => [c.key, { event: c.events[0].key, text: "" }]),
    ),
  };
}

export interface BuiltForm {
  /** `null` until age and sex are valid and at least one result is valid. */
  request: ScoreRequest | null;
  /** By field: "age", or a component key. Only fields with bad text appear. */
  errors: Record<string, string>;
}

export function buildScoreRequest(state: FormState): BuiltForm {
  const errors: Record<string, string> = {};

  const age = parseAge(state.age);
  if ("error" in age) errors.age = age.error;

  const values: Record<string, number> = {};
  for (const component of COMPONENTS) {
    const input = state.components[component.key];
    const event = component.events.find((e) => e.key === input.event);
    if (event === undefined) continue;
    const parsed = parseResult(event.kind, input.text);
    if ("error" in parsed) errors[component.key] = parsed.error;
    else if ("value" in parsed) values[event.key] = parsed.value;
  }

  // Narrowing on `age` and `sex` here also gives the request below its types.
  if (!("value" in age) || state.sex === null || Object.keys(values).length === 0) {
    return { request: null, errors };
  }

  return {
    request: {
      profile: { age: age.value, sex: state.sex, is_afspecwar_eod: state.isAfspecwarEod },
      results: { values },
    },
    errors,
  };
}
