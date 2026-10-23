import { ErrorBox } from "@/components/ErrorBox";
import { COMPONENTS, findEvent } from "@/lib/events";
import { formatPoints as points, minimumNote, pointsNote, scaledNote, walkNote } from "@/lib/format";
import { formatTime } from "@/lib/time";
import type { ComponentScore, ScoreReport, WalkScore } from "@/lib/types";

interface Props {
  report: ScoreReport | null;
  error: unknown;
  /** True while the shown answer is older than the form. */
  pending: boolean;
  /** Send the same request again after a failure. */
  onRetry: () => void;
}

const capitalize = (text: string) => text.charAt(0).toUpperCase() + text.slice(1);

type Status = "good" | "partial" | "bad";

/** Text color for each status. The icon uses the same color, through `currentColor`. */
const STATUS_COLOR: Record<Status, string> = {
  good: "text-green-700 dark:text-green-400",
  partial: "text-amber-700 dark:text-amber-400",
  bad: "text-red-700 dark:text-red-400",
};

/**
 * The mark under a component's points. A component with a minimum is good or bad by that minimum.
 * One with no minimum (body composition) goes by the points it earned.
 */
function rowStatus(scored: ComponentScore): { status: Status; text: string } | null {
  const kind = findEvent(scored.event)?.kind;
  if (kind === undefined) {
    return null;
  }
  const minimum = minimumNote(kind, scored);
  if (minimum !== null) {
    return { status: minimum.met ? "good" : "bad", text: minimum.text };
  }
  const note = pointsNote(kind, scored);
  const status = { full: "good", partial: "partial", none: "bad" } as const;
  return { status: status[note.tone], text: note.text };
}

export function ScoreResult({ report, error, pending, onRetry }: Props) {
  return (
    <section
      aria-live="polite"
      aria-labelledby="result-heading"
      className={`rounded-lg border border-zinc-300 p-4 dark:border-zinc-700 ${
        pending ? "opacity-60" : ""
      }`}
    >
      <h2 id="result-heading" className="text-lg font-semibold">
        Your score
      </h2>

      {error !== null && error !== undefined ? (
        <ErrorBox error={error} onRetry={onRetry} />
      ) : report === null ? (
        <p className="mt-2 text-zinc-600 dark:text-zinc-400">
          {/* The first answer can take a few seconds while the API wakes from idle. */}
          {pending ? "Scoring..." : "Enter your age, sex, and one result."}
        </p>
      ) : (
        <Report report={report} />
      )}
    </section>
  );
}

function Report({ report }: { report: ScoreReport }) {
  const scaled = scaledNote(report);
  return (
    <div className="mt-2 flex flex-col gap-3">
      {report.total === null ? (
        <p className="text-zinc-600 dark:text-zinc-400">
          Enter all four components to see your total.
        </p>
      ) : (
        <p className="text-3xl font-semibold">
          {points(report.total)}
          <span className="ml-2 text-lg font-normal">
            {report.category === null ? "" : capitalize(report.category)}
          </span>
        </p>
      )}

      {report.walk !== null && (
        <p className="text-sm text-zinc-600 dark:text-zinc-400">
          {scaled !== null && `${scaled} `}A walker can score up to Satisfactory, not Excellent
          (DAFMAN 36-2905, paras 3.7.3 and 3.10.1).
        </p>
      )}

      <ul className="flex flex-col divide-y divide-zinc-200 dark:divide-zinc-800">
        {COMPONENTS.map((component) => {
          // A walk is pass/fail, so it is in `report.walk`, not in `components`.
          if (component.key === "cardio" && report.walk !== null) {
            return <WalkRow key={component.key} label={component.label} walk={report.walk} />;
          }
          const scored = report.components.find((c) => c.component === component.key);
          const note = scored === undefined ? null : rowStatus(scored);
          return (
            <li key={component.key} className="flex items-baseline justify-between gap-3 py-2">
              <span>
                {component.label}
                {scored !== undefined && (
                  <span className="block text-sm text-zinc-600 dark:text-zinc-400">
                    {findEvent(scored.event)?.label ?? scored.event}
                  </span>
                )}
              </span>
              {scored === undefined ? (
                <span className="text-zinc-600 dark:text-zinc-400">Not entered</span>
              ) : (
                <span className="text-right">
                  <span className="inline-flex items-center gap-1.5">
                    {points(scored.points)} / {scored.max_points}
                    {note !== null && <StatusIcon status={note.status} />}
                  </span>
                  {note !== null && (
                    <span className={`block text-sm font-medium ${STATUS_COLOR[note.status]}`}>
                      {note.text}
                    </span>
                  )}
                </span>
              )}
            </li>
          );
        })}
      </ul>

      {report.assumptions.length > 0 && (
        <ul className="flex flex-col gap-1 text-sm text-zinc-600 dark:text-zinc-400">
          {report.assumptions.map((text) => (
            <li key={text}>Assumption: {text}</li>
          ))}
        </ul>
      )}

      <p className="text-sm text-zinc-600 dark:text-zinc-400">
        Charts effective {report.effective_date}
      </p>
    </div>
  );
}

function WalkRow({ label, walk }: { label: string; walk: WalkScore }) {
  const note = walkNote(walk);
  const status: Status = note.passed ? "good" : "bad";
  return (
    <li className="flex items-baseline justify-between gap-3 py-2">
      <span>
        {label}
        <span className="block text-sm text-zinc-600 dark:text-zinc-400">2 km walk</span>
      </span>
      <span className="text-right">
        <span className="inline-flex items-center gap-1.5">
          {formatTime(walk.result)}
          <StatusIcon status={status} />
        </span>
        <span className={`block text-sm font-medium ${STATUS_COLOR[status]}`}>{note.text}</span>
      </span>
    </li>
  );
}

/** Decorative: the text under the points says the same thing, so color is never the only cue. */
function StatusIcon({ status }: { status: Status }) {
  return (
    <svg
      aria-hidden="true"
      viewBox="0 0 20 20"
      className={`h-4 w-4 ${STATUS_COLOR[status]}`}
      fill="none"
      stroke="currentColor"
      strokeWidth="2.5"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      {status === "good" && <path d="M4 10.5l4 4 8-9" />}
      {status === "partial" && <path d="M5 10h10" />}
      {status === "bad" && <path d="M5 5l10 10M15 5L5 15" />}
    </svg>
  );
}
