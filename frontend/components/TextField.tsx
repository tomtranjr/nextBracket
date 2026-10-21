import { useId } from "react";

const INPUT =
  "min-h-11 w-full rounded-md border bg-transparent px-3 text-base " +
  "border-zinc-300 dark:border-zinc-700";
const INPUT_BAD = "border-red-600 dark:border-red-400";

interface TextFieldProps {
  label: string;
  inputMode: "numeric" | "decimal";
  placeholder: string;
  value: string;
  error: string | undefined;
  /** Plain help under the input, for example how the form read the text. */
  note?: string | null;
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
  note,
  onChange,
}: TextFieldProps) {
  const id = useId();
  const errorId = `${id}-error`;
  const noteId = `${id}-note`;
  const describedBy = [
    error === undefined ? null : errorId,
    note ? noteId : null,
  ].filter((part) => part !== null);
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
        aria-describedby={describedBy.length === 0 ? undefined : describedBy.join(" ")}
        className={`${INPUT} ${error === undefined ? "" : INPUT_BAD}`}
        onChange={(e) => onChange(e.target.value)}
      />
      {error !== undefined && (
        <p id={errorId} className="text-sm text-red-700 dark:text-red-400">
          {error}
        </p>
      )}
      {note && (
        <p id={noteId} className="text-sm text-zinc-600 dark:text-zinc-400">
          {note}
        </p>
      )}
    </div>
  );
}
