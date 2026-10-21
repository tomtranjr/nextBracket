import { describe, expect, it } from "vitest";

import { liveView } from "@/lib/use-live-answer";

const failure = new Error("down");

describe("liveView", () => {
  it("is empty when there is nothing to send", () => {
    expect(liveView(null, { key: "a", value: 1 })).toEqual({
      value: null,
      error: null,
      pending: false,
    });
  });

  it("is pending with nothing to show before the first answer", () => {
    expect(liveView("a", null)).toEqual({ value: null, error: null, pending: true });
  });

  it("shows the answer for the current key", () => {
    expect(liveView("a", { key: "a", value: 1 })).toEqual({
      value: 1,
      error: null,
      pending: false,
    });
  });

  it("shows the error for the current key", () => {
    expect(liveView("a", { key: "a", error: failure })).toEqual({
      value: null,
      error: failure,
      pending: false,
    });
  });

  // A new request is on its way, so the old failure may no longer be true.
  it("hides an error for an older key while the new one is pending", () => {
    expect(liveView("b", { key: "a", error: failure })).toEqual({
      value: null,
      error: null,
      pending: true,
    });
  });

  // The old score stays on screen, dimmed, so the card does not flash empty while typing.
  it("keeps an older value while the new one is pending", () => {
    expect(liveView("b", { key: "a", value: 1 })).toEqual({
      value: 1,
      error: null,
      pending: true,
    });
  });
});
