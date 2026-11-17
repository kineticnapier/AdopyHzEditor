import assert from "node:assert/strict";
import test from "node:test";
import { formatTrackHoverReadout } from "../src/editor/trackHoverReadout.ts";

test("Track hover shows a percentage without a currency marker", () => {
  assert.equal(
    formatTrackHoverReadout({ id: 7, noteName: "C4", duration: 0.25, magnitude: 0.35 }),
    "Track #7 · C4 · 0.250 s · 35.0%",
  );
});

test("Track hover handles zero and full magnitude", () => {
  assert.equal(
    formatTrackHoverReadout({ id: 0, noteName: "A4", duration: 1, magnitude: 0 }),
    "Track #0 · A4 · 1.000 s · 0.0%",
  );
  assert.equal(
    formatTrackHoverReadout({ id: 9, noteName: "A4", duration: 1, magnitude: 1 }),
    "Track #9 · A4 · 1.000 s · 100.0%",
  );
});
