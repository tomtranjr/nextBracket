import type { EventKind } from "./events";
import { formatRatio } from "./score-form";
import { formatTime } from "./time";
import type { ComponentScore } from "./types";

/** Points can be halves (87.5). Show a decimal only when there is one. */
export function formatPoints(n: number): string {
  return Number.isInteger(n) ? String(n) : n.toFixed(1);
}

/** Show a stored result the way a person types it: seconds as m:ss, hundredths as a ratio. */
export function formatResult(kind: EventKind, value: number): string {
  switch (kind) {
    case "time":
      return formatTime(value);
    case "ratio":
      return formatRatio(value);
    case "reps":
      return String(value);
  }
}

/**
 * The line under a component's points: the minimum, and on a miss how far off the result is.
 * Returns null when the component has no minimum. The gap is a distance, so the text needs no
 * "faster" or "more" and works for both lower-is-better and higher-is-better events.
 */
export function minimumNote(
  kind: EventKind,
  scored: Pick<ComponentScore, "minimum_met" | "minimum" | "minimum_gap">,
): { met: boolean; text: string } | null {
  if (scored.minimum === null || scored.minimum_met === null) {
    return null;
  }
  const minimum = formatResult(kind, scored.minimum);
  if (scored.minimum_met) {
    return { met: true, text: `Minimum ${minimum} met` };
  }
  // A miss always has a gap. Fall back to no gap text rather than invent one.
  const by = scored.minimum_gap === null ? "" : ` by ${formatResult(kind, scored.minimum_gap)}`;
  return { met: false, text: `Below minimum ${minimum}${by}` };
}
