import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

import { COMPONENTS, findEvent } from "@/lib/events";

// Drift check: lib/events.ts is written by hand, so read the real standards files and compare.
// CI checks out the whole repo, so this path exists there too.
const STANDARDS_DIR = fileURLToPath(new URL("../../backend/data/standards", import.meta.url));

interface StandardsFile {
  version: string;
  components: Record<string, { max_points: number; events: string[] }>;
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
      expect(component.events.map((e) => e.key)).toEqual(expected.events);
      expect(component.max_points).toBe(expected.max_points);
    }
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
