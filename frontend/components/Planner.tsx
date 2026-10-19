"use client";

import { useState } from "react";

import { TextField } from "@/components/TextField";
import { api, errorMessage } from "@/lib/api";
import { formatPoints } from "@/lib/format";
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
import type { BuiltForm, FormState } from "@/lib/score-form";
import type { PlanRequest, PlanResult } from "@/lib/types";
import { useLiveAnswer } from "@/lib/use-live-answer";

const DEBOUNCE_MS = 300;

// Outside the component, so `useLiveAnswer` sees the same function on every render.
const planCall = (key: string, signal: AbortSignal) =>
  api.plan(JSON.parse(key) as PlanRequest, signal);

interface Props {
  /** The calculator form: the planner plans for the same person and results. */
  state: FormState;
  built: BuiltForm;
}

export function Planner({ state, built }: Props) {
  const [targetText, setTargetText] = useState("");

  const target = parseTarget(targetText);
  const request = buildPlanRequest(built, target);
  const key = request === null ? null : JSON.stringify(request);
  const { value: result, error, pending } = useLiveAnswer(key, planCall, DEBOUNCE_MS);
  const hint = planHint(state, built, target);

  return (
    <section
      aria-labelledby="plan-heading"
      className="flex flex-col gap-4 rounded-lg border border-zinc-300 p-4 dark:border-zinc-700"
    >
      <h2 id="plan-heading" className="text-lg font-semibold">
        Reach a target
      </h2>

      <TextField
        label="Target total"
        inputMode="decimal"
        placeholder="90"
        value={targetText}
        error={"error" in target ? target.error : undefined}
        onChange={setTargetText}
      />
      <div className="flex flex-wrap gap-3">
        {TARGET_PRESETS.map((preset) => (
          // type="button", so Enter in the form never submits it.
          <button
            key={preset.value}
            type="button"
            className="min-h-11 rounded-md border border-zinc-300 px-4 dark:border-zinc-700"
            onClick={() => setTargetText(String(preset.value))}
          >
            {preset.label}
          </button>
        ))}
      </div>

      <div aria-live="polite" className={pending ? "opacity-60" : ""}>
        {hint !== null ? (
          <p className="text-zinc-600 dark:text-zinc-400">{hint}</p>
        ) : error !== null ? (
          <p role="alert" className="text-red-700 dark:text-red-400">
            {errorMessage(error)}
          </p>
        ) : result !== null ? (
          <Plan result={result} />
        ) : pending ? (
          <p className="text-zinc-600 dark:text-zinc-400">Working out your options.</p>
        ) : null}
      </div>
    </section>
  );
}

function Plan({ result }: { result: PlanResult }) {
  const status = statusText(result);
  const note = assumptionNote(result.assumed_components);
  const groups = groupOptions(result.options);

  return (
    <div className="flex flex-col gap-4">
      {status !== null && <p>{status}</p>}
      {note !== null && <p className="text-sm text-zinc-600 dark:text-zinc-400">{note}</p>}

      {groups.map((group) => (
        <div key={group.kind} className="flex flex-col gap-2">
          <h3 className="font-semibold">{group.heading}</h3>
          <p className="text-sm text-zinc-600 dark:text-zinc-400">{group.text}</p>
          <ul className="flex flex-col gap-3">
            {group.options.map((option, index) => (
              <li
                key={index}
                className="rounded-md border border-zinc-200 p-3 dark:border-zinc-800"
              >
                <ul className="flex flex-col gap-1">
                  {option.changes.map((change) => (
                    <li key={change.event}>{formatChange(change)}</li>
                  ))}
                </ul>
                <p className="mt-2 text-sm text-zinc-600 dark:text-zinc-400">
                  Projected total {formatPoints(option.projected_total)}
                </p>
              </li>
            ))}
          </ul>
        </div>
      ))}

      <p className="text-sm text-zinc-600 dark:text-zinc-400">
        Charts effective {result.effective_date}
      </p>
    </div>
  );
}
