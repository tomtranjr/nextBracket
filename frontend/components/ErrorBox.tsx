import { errorMessage } from "@/lib/api";

interface Props {
  error: unknown;
  onRetry: () => void;
}

/** A failed call: what went wrong, and a button to send the same request again. */
export function ErrorBox({ error, onRetry }: Props) {
  return (
    <div className="mt-2 flex flex-col items-start gap-2">
      <p role="alert" className="text-red-700 dark:text-red-400">
        {errorMessage(error)}
      </p>
      {/* type="button", so Enter in the form never submits it. */}
      <button
        type="button"
        className="min-h-11 rounded-md border border-zinc-300 px-4 dark:border-zinc-700"
        onClick={onRetry}
      >
        Try again
      </button>
    </div>
  );
}
