/**
 * Join element ids for `aria-describedby`, skipping the ones not shown.
 * Returns `undefined` when none are shown, so React leaves the attribute off.
 */
export function describedBy(...ids: (string | false | undefined)[]): string | undefined {
  const shown = ids.filter((id): id is string => typeof id === "string" && id !== "");
  return shown.length === 0 ? undefined : shown.join(" ");
}
