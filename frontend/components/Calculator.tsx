"use client";

import { useState } from "react";

import { Planner } from "@/components/Planner";
import { ScoreResult } from "@/components/ScoreResult";
import { TextField } from "@/components/TextField";
import { api } from "@/lib/api";
import { COMPONENTS, type ComponentInfo } from "@/lib/events";
import {
  buildScoreRequest,
  formatRatio,
  initialFormState,
  MAX_AGE,
  MIN_AGE,
  timeReadAsText,
  truncatedRatioText,
} from "@/lib/score-form";
import type { FormState, WhtrFromInches, WhtrMode } from "@/lib/score-form";
import type { ScoreRequest, Sex } from "@/lib/types";
import { useLiveAnswer } from "@/lib/use-live-answer";

const DEBOUNCE_MS = 300;

// Outside the component, so `useLiveAnswer` sees the same function on every render.
const scoreCall = (key: string, signal: AbortSignal) =>
  api.score(JSON.parse(key) as ScoreRequest, signal);

export function Calculator() {
  const [state, setState] = useState<FormState>(initialFormState);

  const built = buildScoreRequest(state);
  const { request, errors, whtr } = built;
  // The key is a string, so the debounce and the effect compare by value, not by identity.
  const key = request === null ? null : JSON.stringify(request);
  const { value: report, error, pending } = useLiveAnswer(key, scoreCall, DEBOUNCE_MS);

  function update(change: (next: FormState) => void) {
    setState((previous) => {
      const next = structuredClone(previous);
      change(next);
      return next;
    });
  }

  return (
    <div className="flex flex-col gap-6">
      <form className="flex flex-col gap-6" onSubmit={(event) => event.preventDefault()}>
        <fieldset className="flex flex-col gap-4">
          <legend className="mb-2 text-lg font-semibold">About you</legend>
          <TextField
            label="Age"
            inputMode="numeric"
            placeholder={`${MIN_AGE} to ${MAX_AGE}`}
            value={state.age}
            error={errors.age}
            onChange={(age) => update((s) => void (s.age = age))}
          />
          <RadioGroup
            legend="Sex"
            name="sex"
            options={[
              { value: "M", label: "Male" },
              { value: "F", label: "Female" },
            ]}
            value={state.sex}
            onChange={(sex) => update((s) => void (s.sex = sex as Sex))}
          />
          <label className="flex items-start gap-3">
            <input
              type="checkbox"
              className="mt-1 size-5"
              checked={state.isAfspecwarEod}
              onChange={(e) => update((s) => void (s.isAfspecwarEod = e.target.checked))}
            />
            <span>
              I am AFSPECWAR/EOD
              <span className="block text-sm text-zinc-600 dark:text-zinc-400">
                Uses the AFSPECWAR/EOD chart. Body composition uses your own sex and age.
              </span>
            </span>
          </label>
        </fieldset>

        {COMPONENTS.map((component) =>
          component.key === "body_comp" ? (
            <BodyCompFields
              key={component.key}
              component={component}
              state={state.whtr}
              ratioText={state.components.body_comp.text}
              errors={errors}
              whtr={whtr}
              onMode={(mode) =>
                // The two ways to enter it do not share values, so a switch starts clean.
                update((s) => {
                  s.whtr = { mode, waist: "", height: "" };
                  s.components.body_comp.text = "";
                })
              }
              onRatio={(text) => update((s) => void (s.components.body_comp.text = text))}
              onWaist={(waist) => update((s) => void (s.whtr.waist = waist))}
              onHeight={(height) => update((s) => void (s.whtr.height = height))}
            />
          ) : (
          <ComponentFields
            key={component.key}
            component={component}
            event={state.components[component.key].event}
            text={state.components[component.key].text}
            error={errors[component.key]}
            onEvent={(event) =>
              // A new event has a different unit, so the old text no longer applies.
              update((s) => void (s.components[component.key] = { event, text: "" }))
            }
            onText={(text) => update((s) => void (s.components[component.key].text = text))}
          />
          ),
        )}
      </form>

      <ScoreResult report={report} error={error} pending={pending} />
      <Planner state={state} built={built} />
    </div>
  );
}

interface ComponentFieldsProps {
  component: ComponentInfo;
  event: string;
  text: string;
  error: string | undefined;
  onEvent: (event: string) => void;
  onText: (text: string) => void;
}

function ComponentFields({
  component,
  event,
  text,
  error,
  onEvent,
  onText,
}: ComponentFieldsProps) {
  const chosen = component.events.find((e) => e.key === event) ?? component.events[0];
  const placeholder = { reps: "Reps", time: "m:ss", ratio: "0.50" }[chosen.kind];
  // Phone number keypads have no ":" key. The decimal keypad has ".", and the form reads
  // "15.40" and "1540" too, so a time can be typed on any phone.
  const inputMode = chosen.kind === "reps" ? "numeric" : "decimal";
  const readAs = chosen.kind === "time" ? timeReadAsText(text) : null;

  return (
    <fieldset className="flex flex-col gap-3">
      <legend className="mb-2 text-lg font-semibold">
        {component.label}{" "}
        <span className="font-normal text-zinc-600 dark:text-zinc-400">
          ({component.max_points} points)
        </span>
      </legend>
      {component.events.length > 1 && (
        <RadioGroup
          legend="Event"
          name={`event-${component.key}`}
          options={component.events.map((e) => ({ value: e.key, label: e.label }))}
          value={chosen.key}
          onChange={onEvent}
        />
      )}
      <TextField
        label={chosen.label}
        inputMode={inputMode}
        placeholder={placeholder}
        value={text}
        error={error}
        note={readAs === null ? null : `Read as ${readAs}.`}
        onChange={onText}
      />
    </fieldset>
  );
}

interface BodyCompFieldsProps {
  component: ComponentInfo;
  state: FormState["whtr"];
  ratioText: string;
  errors: Record<string, string>;
  whtr: WhtrFromInches | null;
  onMode: (mode: WhtrMode) => void;
  onRatio: (text: string) => void;
  onWaist: (text: string) => void;
  onHeight: (text: string) => void;
}

// Body composition is one event (WHtR) with two ways to enter it: the ratio, or waist and height.
function BodyCompFields({
  component,
  state,
  ratioText,
  errors,
  whtr,
  onMode,
  onRatio,
  onWaist,
  onHeight,
}: BodyCompFieldsProps) {
  // Set only when the typed ratio has more than two decimals and some digits are dropped.
  const truncated = truncatedRatioText(ratioText);
  return (
    <fieldset className="flex flex-col gap-3">
      <legend className="mb-2 text-lg font-semibold">
        {component.label}{" "}
        <span className="font-normal text-zinc-600 dark:text-zinc-400">
          ({component.max_points} points)
        </span>
      </legend>
      <RadioGroup
        legend="Enter"
        name="whtr-mode"
        options={[
          { value: "measurements", label: "Waist and height" },
          { value: "ratio", label: "Ratio" },
        ]}
        value={state.mode}
        onChange={(mode) => onMode(mode as WhtrMode)}
      />
      {state.mode === "ratio" ? (
        <>
          <TextField
            label="Waist-to-height ratio"
            inputMode="decimal"
            placeholder="0.50"
            value={ratioText}
            error={errors.body_comp}
            onChange={onRatio}
          />
          {truncated !== null && (
            <p className="text-sm text-zinc-600 dark:text-zinc-400">
              Scored as {truncated}. The ratio is truncated to two decimals (DAFMAN 36-2905, para
              3.15.4.2).
            </p>
          )}
        </>
      ) : (
        <>
          <TextField
            label="Waist (inches)"
            inputMode="decimal"
            placeholder="32.5"
            value={state.waist}
            error={errors.waist}
            onChange={onWaist}
          />
          <TextField
            label="Height (inches)"
            inputMode="decimal"
            placeholder="66"
            value={state.height}
            error={errors.height}
            onChange={onHeight}
          />
          <p className="text-sm text-zinc-600 dark:text-zinc-400">
            Enter the values recorded at your PFRA. DAFMAN rounds the waist down, and the height to
            the nearest, 1/2 inch.
          </p>
          {whtr !== null && (
            <p className="text-sm text-zinc-600 dark:text-zinc-400">
              Ratio {whtr.exact.toFixed(4)}, scored as {formatRatio(whtr.hundredths)}. The ratio is
              truncated to two decimals (DAFMAN 36-2905, para 3.15.4.2).
            </p>
          )}
        </>
      )}
    </fieldset>
  );
}

interface RadioGroupProps {
  legend: string;
  name: string;
  options: { value: string; label: string }[];
  value: string | null;
  onChange: (value: string) => void;
}

// Real radio inputs, so the keyboard and screen readers work with no extra code.
function RadioGroup({ legend, name, options, value, onChange }: RadioGroupProps) {
  return (
    <fieldset className="flex flex-col gap-1">
      <legend className="mb-1">{legend}</legend>
      <div className="flex flex-wrap gap-x-6 gap-y-1">
        {options.map((option) => (
          <label key={option.value} className="flex min-h-11 items-center gap-2">
            <input
              type="radio"
              name={name}
              className="size-5"
              value={option.value}
              checked={value === option.value}
              onChange={() => onChange(option.value)}
            />
            {option.label}
          </label>
        ))}
      </div>
    </fieldset>
  );
}
