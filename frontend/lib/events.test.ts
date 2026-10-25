import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

import { COMPONENTS, findEvent, isPassFail, pointsLabel } from "@/lib/events";

// Drift check: lib/events.ts is written by hand, so read the real standards files and compare.
// CI checks out the whole repo, so this path exists there too.
const STANDARDS_DIR = fileURLToPath(new URL("../../backend/data/standards", import.meta.url));

interface StandardsFile {
  version: string;
  components: Record<string, { max_points: number; events: string[] }>;
  tables: { event: string; higher_is_better: boolean }[];
  walk: unknown[];
}

const files: StandardsFile[] = readdirSync(STANDARDS_DIR)
  .filter((name) => name.endsWith(".json"))
  .map((name) => JSON.parse(readFileSync(join(STANDARDS_DIR, name), "utf8")) as StandardsFile);

describe("events.ts matches backend/data/standards", () => {
  it("finds at least one standards file", () => {
    expect(files.length).toBeGreaterThan(0);
  });

  it.each(files.map((f) => [f.version, f] as const))("version %s", (_version, file) => {
    expect(COMPONENTS.map((c) => c.key)).toEqual(Object.keys(file.components));
    for (const component of COMPONENTS) {
      const expected = file.components[component.key];
      // Pass/fail events are not in the file's `components`. They are checked below.
      const scored = component.events.filter((e) => e.passFail !== true);
      expect(scored.map((e) => e.key)).toEqual(expected.events);
      expect(component.max_points).toBe(expected.max_points);
    }
  });

  // The form rejects 0 for these events, and the API does too (`check_result` in scoring.py).
  it.each(files.map((f) => [f.version, f] as const))("lowerIsBetter in version %s", (_v, file) => {
    for (const table of file.tables) {
      expect([table.event, findEvent(table.event)?.lowerIsBetter === true]).toEqual([
        table.event,
        !table.higher_is_better,
      ]);
    }
    // The walk is a time with no table, so lower is better.
    expect(findEvent("walk_2km")?.lowerIsBetter).toBe(true);
  });

  // The walk fills the cardio slot (WALK_COMPONENT in backend/app/models.py). Its times are in
  // the file's `walk` section.
  it.each(files.map((f) => [f.version, f] as const))("walk_2km in version %s", (_v, file) => {
    expect(file.walk.length).toBeGreaterThan(0);
    const passFail = COMPONENTS.flatMap((c) =>
      c.events.filter((e) => e.passFail === true).map((e) => [c.key, e.key]),
    );
    expect(passFail).toEqual([["cardio", "walk_2km"]]);
  });
});

describe("isPassFail", () => {
  it("is true only for the walk", () => {
    expect(isPassFail("walk_2km")).toBe(true);
    expect(isPassFail("run_2mile")).toBe(false);
    expect(isPassFail("nope")).toBe(false);
  });
});

describe("pointsLabel", () => {
  const cardio = COMPONENTS[0];
  const event = (key: string) => cardio.events.find((e) => e.key === key)!;

  it("shows the component's points for a scored event", () => {
    expect(pointsLabel(cardio, event("run_2mile"))).toBe("50 points");
    expect(pointsLabel(COMPONENTS[1], COMPONENTS[1].events[0])).toBe("15 points");
  });

  it("shows pass/fail with no points for the walk", () => {
    expect(pointsLabel(cardio, event("walk_2km"))).toBe("pass/fail, no points");
  });
});

describe("findEvent", () => {
  it("returns the event for a key", () => {
    expect(findEvent("run_2mile")?.label).toBe("2-mile run");
  });

  it("returns undefined for an unknown key", () => {
    expect(findEvent("nope")).toBeUndefined();
  });
});
