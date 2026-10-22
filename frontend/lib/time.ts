// Times are whole seconds everywhere. The form reads minutes and seconds in two boxes, so
// only display needs this helper.

/** Return `m:ss` text for whole seconds, for example `940` gives `"15:40"`. */
export function formatTime(seconds: number): string {
  if (!Number.isInteger(seconds) || seconds < 0) {
    throw new Error(`seconds must be a whole number, not negative: ${seconds}`);
  }
  const minutes = Math.floor(seconds / 60);
  const rest = seconds % 60;
  return `${minutes}:${String(rest).padStart(2, "0")}`;
}
