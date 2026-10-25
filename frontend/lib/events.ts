// Hand-written mirror of the event keys in backend/data/standards/*.json. A drift test in
// events.test.ts reads those files, so a renamed or added event fails CI instead of the form.
// The 2 km walk is not in the file's `components`: it has its own `walk` section. It is listed
// here under cardio anyway, so the form offers it as a third cardio choice.

/** How a person types the result. `time` is m:ss, `ratio` is a two-decimal WHtR. */
export type EventKind = "reps" | "time" | "ratio";

export interface EventInfo {
  /** The event name the API uses. */
  key: string;
  label: string;
  kind: EventKind;
  /** Pass/fail with no points (the 2 km walk). The report shows it outside `components`. */
  passFail?: true;
  /** A short line shown under the field when this event is chosen. */
  hint?: string;
  /** A lower result is better (a time to finish, or WHtR). Then 0 is a typo, not a top score. */
  lowerIsBetter?: true;
}

export interface ComponentInfo {
  /** The component name the API uses. */
  key: string;
  label: string;
  max_points: number;
  /** A member takes one of these. The first is the default. */
  events: EventInfo[];
}

/** In chart order. */
export const COMPONENTS: ComponentInfo[] = [
  {
    key: "cardio",
    label: "Cardio",
    max_points: 50,
    events: [
      { key: "run_2mile", label: "2-mile run", kind: "time", lowerIsBetter: true },
      { key: "hamr_20m", label: "20m HAMR (shuttles)", kind: "reps" },
      {
        key: "walk_2km",
        label: "2 km walk",
        kind: "time",
        passFail: true,
        lowerIsBetter: true,
        hint: "Only with an AF Form 469 that allows it (DAFMAN 36-2905, para 3.15.12.1).",
      },
    ],
  },
  {
    key: "strength",
    label: "Strength",
    max_points: 15,
    events: [
      { key: "push_up", label: "Push-up", kind: "reps" },
      { key: "hand_release_push_up", label: "Hand-release push-up", kind: "reps" },
    ],
  },
  {
    key: "core",
    label: "Core",
    max_points: 15,
    events: [
      { key: "sit_up", label: "Sit-up", kind: "reps" },
      { key: "cross_leg_reverse_crunch", label: "Cross-leg reverse crunch", kind: "reps" },
      { key: "forearm_plank", label: "Forearm plank", kind: "time" },
    ],
  },
  {
    key: "body_comp",
    label: "Body composition",
    max_points: 20,
    events: [{ key: "whtr", label: "Waist-to-height ratio", kind: "ratio", lowerIsBetter: true }],
  },
];

/** The text after a component name: "50 points", or "pass/fail, no points" for the walk. */
export function pointsLabel(component: ComponentInfo, event: EventInfo): string {
  return event.passFail === true ? "pass/fail, no points" : `${component.max_points} points`;
}

/** True for a pass/fail event key (the 2 km walk). */
export function isPassFail(key: string): boolean {
  return findEvent(key)?.passFail === true;
}

/** Find an event by its API name. Used to label rows in a score report. */
export function findEvent(key: string): EventInfo | undefined {
  return COMPONENTS.flatMap((c) => c.events).find((e) => e.key === key);
}
