import { errorMessage } from "@/lib/api";
import { COMPONENTS, findEvent } from "@/lib/events";
import { formatPoints as points } from "@/lib/format";
import type { ScoreReport } from "@/lib/types";

interface Props {
  report: ScoreReport | null;
  error: unknown;
  /** True while the shown answer is older than the form. */
  pending: boolean;
}

const capitalize = (text: string) => text.charAt(0).toUpperCase() + text.slice(1);

export function ScoreResult({ report, error, pending }: Props) {
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
        <p role="alert" className="mt-2 text-red-700 dark:text-red-400">
          {errorMessage(error)}
        </p>
      ) : report === null ? (
        <p className="mt-2 text-zinc-600 dark:text-zinc-400">
          Enter your age, sex, and one result.
        </p>
      ) : (
        <Report report={report} />
      )}
    </section>
  );
}

function Report({ report }: { report: ScoreReport }) {
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

      <ul className="flex flex-col divide-y divide-zinc-200 dark:divide-zinc-800">
        {COMPONENTS.map((component) => {
          const scored = report.components.find((c) => c.component === component.key);
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
                  {points(scored.points)} / {scored.max_points}
                  {scored.minimum_met === false && (
                    <span className="block text-sm font-medium text-red-700 dark:text-red-400">
                      Minimum missed
                    </span>
                  )}
                </span>
              )}
            </li>
          );
        })}
      </ul>

      <p className="text-sm text-zinc-600 dark:text-zinc-400">
        Charts effective {report.effective_date}
      </p>
    </div>
  );
}
