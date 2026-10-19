import type { EventKind } from "./events";
import { formatRatio } from "./score-form";
import { formatTime } from "./time";

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
