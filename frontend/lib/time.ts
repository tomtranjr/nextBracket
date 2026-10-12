// Mirrors backend/app/core/timeparse.py, so the form and the API read `m:ss` the same way.

// Seconds need two digits ("15:05"), so "15:5" cannot be read as 15:50 or 15:05 by mistake.
const TIME = /^(\d{1,3}):([0-5]\d)$/;

/** Return whole seconds for `m:ss` text, for example `"15:40"` gives `940`. Throws on any other shape. */
export function parseTime(text: string): number {
  const match = TIME.exec(text.trim());
  if (match === null) {
    throw new Error(`time must look like m:ss, for example 15:40: ${JSON.stringify(text)}`);
  }
  return Number(match[1]) * 60 + Number(match[2]);
}

/** Return `m:ss` text for whole seconds, for example `940` gives `"15:40"`. */
export function formatTime(seconds: number): string {
  if (!Number.isInteger(seconds) || seconds < 0) {
    throw new Error(`seconds must be a whole number, not negative: ${seconds}`);
  }
  const minutes = Math.floor(seconds / 60);
  const rest = seconds % 60;
  return `${minutes}:${String(rest).padStart(2, "0")}`;
}
