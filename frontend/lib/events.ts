// Hand-written mirror of the event keys in backend/data/standards/*.json. A drift test in
// events.test.ts reads those files, so a renamed or added event fails CI instead of the form.

/** How a person types the result. `time` is m:ss, `ratio` is a two-decimal WHtR. */
export type EventKind = "reps" | "time" | "ratio";

export interface EventInfo {
  /** The event name the API uses. */
  key: string;
  label: string;
  kind: EventKind;
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
      { key: "run_2mile", label: "2-mile run", kind: "time" },
      { key: "hamr_20m", label: "20m HAMR (shuttles)", kind: "reps" },
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
    events: [{ key: "whtr", label: "Waist-to-height ratio", kind: "ratio" }],
  },
];

/** Find an event by its API name. Used to label rows in a score report. */
export function findEvent(key: string): EventInfo | undefined {
  return COMPONENTS.flatMap((c) => c.events).find((e) => e.key === key);
}
