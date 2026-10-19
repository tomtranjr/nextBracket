import { useEffect, useState } from "react";

import { useDebouncedValue } from "./use-debounced-value";

// What came back for one request. `key` is the request as JSON, so a form can tell
// whether the answer on screen belongs to what is typed now.
type Answer<T> = { key: string; value: T } | { key: string; error: unknown };

export interface LiveAnswer<T> {
  /** The answer for the current key, or `null` if there is none yet or the call failed. */
  value: T | null;
  /** The failure for the current key, or `null`. */
  error: unknown;
  /** True while the answer on screen is older than the key. */
  pending: boolean;
}

/**
 * Call the API when `key` stops changing for `ms`, and cancel a call that a newer key replaces.
 * `key` is the request as JSON, or `null` when there is nothing to send. An edit and its undo
 * give the same key, so they send no new request.
 * `call` must be a function that lives outside any component, so the effect does not restart
 * on every render.
 */
export function useLiveAnswer<T>(
  key: string | null,
  call: (key: string, signal: AbortSignal) => Promise<T>,
  ms: number,
): LiveAnswer<T> {
  const [answer, setAnswer] = useState<Answer<T> | null>(null);
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
  }, [debouncedKey, call]);

  // No stored "loading" flag: the answer is pending when it does not match what is typed now.
  const shown = key === null ? null : answer;
  return {
    value: shown !== null && "value" in shown ? shown.value : null,
    error: shown !== null && "error" in shown ? shown.error : null,
    pending: key !== null && answer?.key !== key,
  };
}
