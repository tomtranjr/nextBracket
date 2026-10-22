import { useId } from "react";

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
  onChange,
}: TextFieldProps) {
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
