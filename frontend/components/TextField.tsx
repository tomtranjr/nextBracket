import { useId } from "react";

import { describedBy } from "@/lib/a11y";

// Shared with TimeField, so every box looks the same.
export const INPUT =
  "min-h-11 w-full rounded-md border bg-transparent px-3 text-base " +
  "border-zinc-300 dark:border-zinc-700";
export const INPUT_BAD = "border-red-600 dark:border-red-400";

interface TextFieldProps {
  label: string;
  inputMode: "numeric" | "decimal";
  placeholder: string;
  value: string;
  error: string | undefined;
  /** A short line under the label. Screen readers read it with the box. */
  hint?: string;
  onChange: (text: string) => void;
}

// type="text", not "number": a number input takes "e" and "-" and changes on scroll. The
// parsers in lib/score-form.ts and lib/plan-form.ts do the checking.
export function TextField({
  label,
  inputMode,
  placeholder,
  value,
  error,
  hint,
  onChange,
}: TextFieldProps) {
  const id = useId();
  const errorId = `${id}-error`;
  const hintId = `${id}-hint`;
  return (
    <div className="flex flex-col gap-1">
      <label htmlFor={id}>{label}</label>
      {hint !== undefined && (
        <p id={hintId} className="text-sm text-zinc-600 dark:text-zinc-400">
          {hint}
        </p>
      )}
      <input
        id={id}
        type="text"
        inputMode={inputMode}
        autoComplete="off"
        placeholder={placeholder}
        value={value}
        aria-invalid={error !== undefined}
        aria-describedby={describedBy(hint !== undefined && hintId, error !== undefined && errorId)}
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
