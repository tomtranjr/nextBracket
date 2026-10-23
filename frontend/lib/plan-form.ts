// Pure helpers for the target planner: read the target, build the /plan request, and word the
// answer. No React here, so Vitest can test all of it. The wording lives here on purpose: the
// planner must never state a fact the API did not give (see `statusText`).

import { COMPONENTS, findEvent, isPassFail } from "./events";
import { formatPoints, formatResult } from "./format";
import { parseAge, type BuiltForm, type FormState, type Parsed } from "./score-form";
import type { EventChange, PlanOption, PlanOptionKind, PlanRequest, PlanResult } from "./types";

// Whole points or a half: "90", "87.5", "87.50". Another decimal has no meaning for a total that
// moves in halves, and we do not round (same rule as the WHtR field).
const TARGET = /^(\d{1,3})?(?:\.(\d{1,2}))?$/;

/** Return composite points: "87.5" gives 87.5. Blank is `empty`, not an error. */
export function parseTarget(text: string): Parsed {
  const t = text.trim();
  if (t === "") return { empty: true };
  const match = TARGET.exec(t);
  const message = "Use a whole number or a half point, for example 90 or 87.5.";
  if (match === null || !/\d/.test(t)) return { ok: false, error: message };
  const fraction = (match[2] ?? "").padEnd(2, "0");
  if (fraction !== "00" && fraction !== "50") return { ok: false, error: message };
  const value = Number(match[1] ?? "0") + Number(fraction) / 100;
  if (value > 100) return { ok: false, error: "Target must be 0 to 100." };
  return { ok: true, value };
}

export const TARGET_PRESETS = [
  { label: "Satisfactory (75)", value: 75 },
  { label: "Excellent (90)", value: 90 },
] as const;

// `/plan` returns 422 for a walk (NB-18). Dropping the walk and planning the rest would be wrong
// too: the API would treat cardio as missing and plan a run for a member who cannot run.
export const WALK_PLAN_NOTE = "Planning is not available for the 2 km walk yet.";

/** True when the person picked the walk for cardio, even before typing a time. */
export function walkChosen(state: FormState): boolean {
  return COMPONENTS.some((c) => isPassFail(state.components[c.key]?.event ?? ""));
}

/**
 * Return the `/plan` request, or `null` until age, sex, one result, and a target are valid.
 * Always `null` for a walker (see `WALK_PLAN_NOTE`).
 */
export function buildPlanRequest(
  state: FormState,
  built: BuiltForm,
  target: Parsed,
): PlanRequest | null {
  if (walkChosen(state) || built.request === null || !("value" in target)) return null;
  return {
    profile: built.request.profile,
    target: target.value,
    current: built.request.results,
  };
}

/**
 * Say what is missing before a plan can run, or return `null` when it can. A bad target is
 * `null` too: its own field already shows the error.
 */
export function planHint(state: FormState, built: BuiltForm, target: Parsed): string | null {
  if (walkChosen(state)) return WALK_PLAN_NOTE;
  if (!("value" in parseAge(state.age)) || state.sex === null) return "Enter your age and sex.";
  if (built.request === null) return "Enter at least one result.";
  if ("empty" in target) return "Enter a target.";
  return null;
}

const componentLabel = (key: string) =>
  (COMPONENTS.find((c) => c.key === key)?.label ?? key).toLowerCase();

function listLabels(keys: string[]): string {
  return keys.map(componentLabel).join(", ");
}

/** Tell the person which components the plan guessed, or `null` when it guessed none. */
export function assumptionNote(assumed: string[]): string | null {
  if (assumed.length === 0) return null;
  const start =
    assumed.length === 1 ? "It starts from the minimum." : "It starts from the minimum for each.";
  // Body composition has no minimum, so the API plans it from 0 points.
  const bodyComp = assumed.includes("body_comp") ? " Body composition starts at 0 points." : "";
  return `No result for ${listLabels(assumed)}. ${start}${bodyComp}`;
}

/** Return the text for a plan with no options to list, or `null` when there are options. */
export function statusText(result: PlanResult): string | null {
  const target = formatPoints(result.target);
  switch (result.status) {
    case "options":
      return null;
    case "impossible":
      return (
        `Your target of ${target} is above the best total possible for your profile: ` +
        `${formatPoints(result.max_total)}.`
      );
    case "already_met":
      // The minimums alone can reach a low target, so with a guess in play this is not a fact
      // about the person. Say so, and do not call it a result.
      return result.assumed_components.length > 0
        ? `At the minimums assumed for ${listLabels(result.assumed_components)}, you already ` +
            `reach ${target}. Enter your real results for a true answer.`
        : `You already reach ${target}.`;
  }
}

export interface OptionGroup {
  kind: PlanOptionKind;
  heading: string;
  text: string;
  options: PlanOption[];
}

// No group says "easiest": the quick-wins effort measure is a guess (build plan, PR 11).
const GROUPS: { kind: PlanOptionKind; heading: string; text: string }[] = [
  {
    kind: "single_event",
    heading: "Change one event",
    text: "Raise one event and keep the others as they are.",
  },
  {
    kind: "balanced",
    heading: "Balanced",
    text: "Raise every event a little, one step at a time.",
  },
  {
    kind: "quick_wins",
    heading: "Quick wins",
    text: "Raise the events where the next step earns the most points for its size on the chart.",
  },
];

/** Group the options by kind, in a fixed order. Backend order holds inside a group. */
export function groupOptions(options: PlanOption[]): OptionGroup[] {
  return GROUPS.map((group) => ({
    ...group,
    options: options.filter((option) => option.kind === group.kind),
  })).filter((group) => group.options.length > 0);
}

/** One line for one change: "2-mile run: 15:40 to 14:13 (44 to 47.5 points)". */
export function formatChange(change: EventChange): string {
  const event = findEvent(change.event);
  const show = (value: number) =>
    event === undefined ? String(value) : formatResult(event.kind, value);
  const from =
    change.from_result === null ? "no result (assumed at the minimum)" : show(change.from_result);
  const points = `${formatPoints(change.from_points)} to ${formatPoints(change.to_points)} points`;
  return `${event?.label ?? change.event}: ${from} to ${show(change.to_result)} (${points})`;
}
