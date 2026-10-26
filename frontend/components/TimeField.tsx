import { useId } from "react";

import { INPUT, INPUT_BAD } from "@/components/TextField";
import { describedBy } from "@/lib/a11y";
import type { TimeBox } from "@/lib/score-form";

interface TimeFieldProps {
  /** The event name, for example "2-mile run". Screen readers read it before each box label. */
  label: string;
  minutes: string;
  seconds: string;
  error: string | undefined;
  /** The boxes to mark red. The error line is shared by both. */
  bad: TimeBox[];
  /** A short line under the event name. Screen readers read it with each box. */
  hint?: string;
  onMinutes: (text: string) => void;
  onSeconds: (text: string) => void;
}

// Two boxes, so nobody has to type ":" (phone number keypads have none) and "15.4" cannot be
// read two ways. The form adds minutes x 60 + seconds in lib/score-form.ts.
export function TimeField({
  label,
  minutes,
  seconds,
  error,
  bad,
  hint,
  onMinutes,
  onSeconds,
}: TimeFieldProps) {
  const id = useId();
  const errorId = `${id}-error`;
  const hintId = `${id}-hint`;
  const boxes = [
    { box: "minutes", text: "Minutes", value: minutes, placeholder: "15", onChange: onMinutes },
    { box: "seconds", text: "Seconds", value: seconds, placeholder: "40", onChange: onSeconds },
  ] as const;
  return (
    <fieldset className="flex flex-col gap-1">
      <legend className="mb-1">{label}</legend>
      {hint !== undefined && (
        <p id={hintId} className="text-sm text-zinc-600 dark:text-zinc-400">
          {hint}
        </p>
      )}
      <div className="grid grid-cols-2 gap-3">
        {boxes.map(({ box, text, value, placeholder, onChange }) => {
          const invalid = bad.includes(box);
          return (
            <div key={box} className="flex flex-col gap-1">
              <label htmlFor={`${id}-${box}`} className="text-sm">
                {text}
              </label>
              <input
                id={`${id}-${box}`}
                type="text"
                inputMode="numeric"
                autoComplete="off"
                placeholder={placeholder}
                value={value}
                aria-invalid={invalid}
                aria-describedby={describedBy(
                  hint !== undefined && hintId,
                  error !== undefined && errorId,
                )}
                className={`${INPUT} ${invalid ? INPUT_BAD : ""}`}
                onChange={(e) => onChange(e.target.value)}
              />
            </div>
          );
        })}
      </div>
      {error !== undefined && (
        <p id={errorId} className="text-sm text-red-700 dark:text-red-400">
          {error}
        </p>
      )}
    </fieldset>
  );
}
