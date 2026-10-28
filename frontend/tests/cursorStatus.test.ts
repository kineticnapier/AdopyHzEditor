import assert from "node:assert/strict";
import test from "node:test";
import { formatCursorPeakLabel } from "../src/editor/cursorStatus.ts";

test("out-of-range cursor hides the fabricated boundary peak", () => {
  const label = formatCursorPeakLabel({
    available: true, peakAvailable: false, time: 0.25,
    cursorMidi: 48.25, cursorName: "C3", cursorCents: 25, cursorHz: 132,
  });
  assert.match(label ?? "", /解析音域外/);
  assert.doesNotMatch(label ?? "", /近傍 C/);
});

test("in-range cursor retains peak details", () => {
  const label = formatCursorPeakLabel({
    available: true, peakAvailable: true, peakName: "C4",
    peakCents: 0, peakHz: 261.63, peakDb: -3,
  });
  assert.match(label ?? "", /近傍 C4/);
  assert.match(label ?? "", /261\.63 Hz/);
});
