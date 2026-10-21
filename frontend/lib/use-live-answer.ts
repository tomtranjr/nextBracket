import { useCallback, useEffect, useState } from "react";

import { useDebouncedValue } from "./use-debounced-value";

// What came back for one request. `key` is the request as JSON, so a form can tell
// whether the answer on screen belongs to what is typed now.
export type Answer<T> = { key: string; value: T } | { key: string; error: unknown };

export interface LiveView<T> {
  /** The latest answer, or `null`. While pending it can belong to an older key (shown dimmed). */
  value: T | null;
  /** The failure for the current key, or `null`. */
  error: unknown;
  /** True while the answer on screen is older than the key. */
  pending: boolean;
}

export interface LiveAnswer<T> extends LiveView<T> {
  /** Send the current request again now. For a "Try again" button after a failure. */
  retry: () => void;
}

/**
 * What to show for `key`, given the last answer. Pure, so Vitest can test it without a DOM.
 * An old value stays while a new one is pending, so the card does not flash empty. An old
 * error does not: a new request is on its way, and the failure may no longer be true.
 */
export function liveView<T>(key: string | null, answer: Answer<T> | null): LiveView<T> {
  if (key === null) return { value: null, error: null, pending: false };
  const pending = answer?.key !== key;
  if (answer === null || "error" in answer) {
    return { value: null, error: pending || answer === null ? null : answer.error, pending };
  }
  return { value: answer.value, error: null, pending };
}

/**
 * Call the API when `key` stops changing for `ms`, and cancel a call that a newer key replaces.
 * `key` is the request as JSON, or `null` when there is nothing to send. An edit and its undo
 * give the same key, so they send no new request. `retry` is the way to resend the same key.
 * `call` must be a function that lives outside any component, so the effect does not restart
 * on every render.
 */
export function useLiveAnswer<T>(
  key: string | null,
  call: (key: string, signal: AbortSignal) => Promise<T>,
  ms: number,
): LiveAnswer<T> {
  const [answer, setAnswer] = useState<Answer<T> | null>(null);
  // Bumped by `retry`. It is in the effect deps, so the same key is sent again.
  const [attempt, setAttempt] = useState(0);
  const debouncedKey = useDebouncedValue(key, ms);

  useEffect(() => {
    if (debouncedKey === null) return;
    const controller = new AbortController();
    call(debouncedKey, controller.signal).then(
      (value) => setAnswer({ key: debouncedKey, value }),
      (error: unknown) => {
        // The cleanup below aborts a replaced request. That is not a failure to show.
        if (!controller.signal.aborted) setAnswer({ key: debouncedKey, error });
      },
    );
    return () => controller.abort();
  }, [debouncedKey, call, attempt]);

  const retry = useCallback(() => {
    // Clearing the answer makes the view pending, so the error goes away at once.
    setAnswer(null);
    setAttempt((n) => n + 1);
  }, []);

  return { ...liveView(key, answer), retry };
}
