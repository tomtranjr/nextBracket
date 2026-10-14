"use client";

import { useEffect, useId, useState } from "react";

import { ScoreResult } from "@/components/ScoreResult";
import { api } from "@/lib/api";
import { COMPONENTS, type ComponentInfo } from "@/lib/events";
import {
  buildScoreRequest,
  formatRatio,
  initialFormState,
  MAX_AGE,
  MIN_AGE,
} from "@/lib/score-form";
import type { FormState, WhtrFromInches, WhtrMode } from "@/lib/score-form";
import type { ScoreReport, ScoreRequest, Sex } from "@/lib/types";
import { useDebouncedValue } from "@/lib/use-debounced-value";

const DEBOUNCE_MS = 300;

// What came back for one request. `key` is the request as JSON, so the form can tell
// whether the answer on screen belongs to what is typed now.
type Answer = { key: string; report: ScoreReport } | { key: string; error: unknown };

const INPUT =
  "min-h-11 w-full rounded-md border bg-transparent px-3 text-base " +
  "border-zinc-300 dark:border-zinc-700";
const INPUT_BAD = "border-red-600 dark:border-red-400";

export function Calculator() {
  const [state, setState] = useState<FormState>(initialFormState);
  const [answer, setAnswer] = useState<Answer | null>(null);

  const { request, errors, whtr } = buildScoreRequest(state);
  // The key is a string, so the debounce and the effect compare by value, not by identity.
  // An edit and its undo give the same key, so they send no new request.
  const key = request === null ? null : JSON.stringify(request);
  const debouncedKey = useDebouncedValue(key, DEBOUNCE_MS);

  useEffect(() => {
    if (debouncedKey === null) return;
    const controller = new AbortController();
    api.score(JSON.parse(debouncedKey) as ScoreRequest, controller.signal).then(
      (report) => setAnswer({ key: debouncedKey, report }),
      (error: unknown) => {
        // The cleanup below aborts a replaced request. That is not a failure to show.
        if (!controller.signal.aborted) setAnswer({ key: debouncedKey, error });
      },
    );
    return () => controller.abort();
  }, [debouncedKey]);

  // No stored "loading" flag: the answer is pending when it does not match what is typed now.
  const shown = key === null ? null : answer;
  const pending = key !== null && answer?.key !== key;

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

      <ScoreResult
        report={shown !== null && "report" in shown ? shown.report : null}
        error={shown !== null && "error" in shown ? shown.error : null}
        pending={pending}
      />
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
        inputMode={chosen.kind === "ratio" ? "decimal" : "numeric"}
        placeholder={placeholder}
        value={text}
        error={error}
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
          { value: "ratio", label: "Ratio" },
          { value: "measurements", label: "Waist and height" },
        ]}
        value={state.mode}
        onChange={(mode) => onMode(mode as WhtrMode)}
      />
      {state.mode === "ratio" ? (
        <TextField
          label="Waist-to-height ratio"
          inputMode="decimal"
          placeholder="0.50"
          value={ratioText}
          error={errors.body_comp}
          onChange={onRatio}
        />
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
          {whtr !== null && (
            <p className="text-sm text-zinc-600 dark:text-zinc-400">
              Ratio {whtr.exact.toFixed(4)}, scored as {formatRatio(whtr.hundredths)}. The ratio is
              rounded to two decimals. DAFMAN has not confirmed this rule yet.
            </p>
          )}
        </>
      )}
    </fieldset>
  );
}

interface TextFieldProps {
  label: string;
  inputMode: "numeric" | "decimal";
  placeholder: string;
  value: string;
  error: string | undefined;
  onChange: (text: string) => void;
}

// type="text", not "number": a number input takes "e" and "-" and changes on scroll. The
// parsers in lib/score-form.ts do the checking.
function TextField({ label, inputMode, placeholder, value, error, onChange }: TextFieldProps) {
  const id = useId();
  const errorId = `${id}-error`;
  return (
    <div className="flex flex-col gap-1">
      <label htmlFor={id}>{label}</label>
      <input
        id={id}
        type="text"
        inputMode={inputMode}
        autoComplete="off"
        placeholder={placeholder}
        value={value}
        aria-invalid={error !== undefined}
        aria-describedby={error === undefined ? undefined : errorId}
        className={`${INPUT} ${error === undefined ? "" : INPUT_BAD}`}
        onChange={(e) => onChange(e.target.value)}
      />
      {error !== undefined && (
        <p id={errorId} className="text-sm text-red-700 dark:text-red-400">
          {error}
        </p>
      )}
    </div>
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
