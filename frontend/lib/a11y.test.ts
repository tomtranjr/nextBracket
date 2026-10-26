import { describe, expect, it } from "vitest";

import { describedBy } from "@/lib/a11y";

describe("describedBy", () => {
  it("joins the shown ids, hint first", () => {
    expect(describedBy("f-hint", "f-error")).toBe("f-hint f-error");
  });

  it("skips ids that are not shown", () => {
    expect(describedBy("f-hint", false)).toBe("f-hint");
    expect(describedBy(false, "f-error")).toBe("f-error");
    expect(describedBy(undefined, "")).toBeUndefined();
  });

  it("is undefined when nothing is shown, so the attribute is left off", () => {
    expect(describedBy(false, false)).toBeUndefined();
  });
});
