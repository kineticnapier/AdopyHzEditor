import assert from "node:assert/strict";
import test from "node:test";
import { wheelViewChange, type WheelInput } from "../src/editor/wheelNavigation.ts";
import type { ViewState } from "../src/editor/bridge.ts";

const view: ViewState = {
  mode: "both", start: 20, windowSeconds: 12, pitchBottom: 40, visibleNotes: 48,
};

function wheel(deltaX: number, deltaY: number, changes: Partial<WheelInput> = {}): WheelInput {
  return {
    deltaX, deltaY, deltaMode: 0, shiftKey: false, altKey: false, ctrlKey: false,
    ...changes,
  };
}

test("horizontal-only gestures pan in opposite directions", () => {
  const right = wheelViewChange(wheel(80, 0), view);
  const left = wheelViewChange(wheel(-80, 0), view);
  assert.ok(right?.start !== undefined && left?.start !== undefined);
  assert.ok(right.start > view.start);
  assert.ok(left.start < view.start);
  assert.ok(Math.abs((right.start - view.start) + (left.start - view.start)) < 1e-9);
});

test("vertical wheel retains existing pan, pitch scroll, and zoom behavior", () => {
  assert.deepEqual(wheelViewChange(wheel(0, 120), view), { start: 20.96 });
  assert.deepEqual(wheelViewChange(wheel(0, -120), view), { start: 19.04 });
  assert.deepEqual(wheelViewChange(wheel(0, -120, { shiftKey: true }), view), { pitchBottom: 43 });
  assert.deepEqual(wheelViewChange(wheel(0, -120, { altKey: true }), view), { visibleNotes: 44, pitchBottom: 40 });
  assert.deepEqual(wheelViewChange(wheel(0, -120, { ctrlKey: true }), view), { windowSeconds: 10.2 });
});

test("horizontal gestures with modifiers never trigger vertical zoom or pitch scroll", () => {
  for (const key of ["ctrlKey", "altKey", "shiftKey"] as const) {
    const change = wheelViewChange(wheel(-120, 0, { [key]: true }), view);
    assert.deepEqual(change, { start: 19.04 });
  }
});

test("dominant axis determines diagonal trackpad gesture", () => {
  assert.ok((wheelViewChange(wheel(-80, 10), view)?.start ?? Infinity) < view.start);
  assert.deepEqual(wheelViewChange(wheel(-10, 80), view), { start: 20.64 });
});

test("zero movement is ignored and line-mode horizontal scrolling is supported", () => {
  assert.equal(wheelViewChange(wheel(0, 0), view), null);
  assert.deepEqual(wheelViewChange(wheel(3, 0, { deltaMode: 1 }), view), { start: 20.96 });
});


test("small pixel deltas pan proportionally instead of a full wheel step", () => {
  const onePixel = wheelViewChange(wheel(0, 1), view);
  const oneTick = wheelViewChange(wheel(0, 120), view);
  assert.ok(onePixel?.start !== undefined && oneTick?.start !== undefined);
  assert.ok(Math.abs((onePixel.start - view.start) * 120 - (oneTick.start - view.start)) < 1e-10);
  assert.ok(Math.abs((wheelViewChange(wheel(0, -1), view)?.start ?? NaN) - (view.start - .008)) < 1e-10);
});

test("vertical line and page deltas normalize to one nominal tick", () => {
  assert.deepEqual(wheelViewChange(wheel(0, 3, { deltaMode: 1 }), view), { start: 20.96 });
  assert.deepEqual(wheelViewChange(wheel(0, -1, { deltaMode: 2 }), view), { start: 19.04 });
});

test("Ctrl trackpad zoom scales with delta and preserves pointer time", () => {
  const anchor = { timeRatio: .75, pitchRatio: .5 };
  const change = wheelViewChange(wheel(0, -60, { ctrlKey: true }), view, anchor);
  assert.ok(change?.windowSeconds !== undefined && change.start !== undefined);
  assert.ok(Math.abs(change.windowSeconds - view.windowSeconds * Math.sqrt(.85)) < 1e-10);
  assert.ok(Math.abs(change.start + anchor.timeRatio * change.windowSeconds -
    (view.start + anchor.timeRatio * view.windowSeconds)) < 1e-10);
  const out = wheelViewChange(wheel(0, 60, { ctrlKey: true }), view);
  assert.ok(Math.abs((out?.windowSeconds ?? NaN) - view.windowSeconds * Math.sqrt(1.18)) < 1e-10);
});

test("tiny Shift wheel deltas accumulate to one pitch step without a full-step jump", () => {
  const accumulator = { modifier: null, remainder: 0 } as import("../src/editor/wheelNavigation.ts").WheelPitchAccumulator;
  let current = { ...view };
  for (let i = 0; i < 39; i++) {
    assert.equal(wheelViewChange(wheel(0, -1, { shiftKey: true }), current, undefined, accumulator), null);
  }
  const change = wheelViewChange(wheel(0, -1, { shiftKey: true }), current, undefined, accumulator);
  assert.deepEqual(change, { pitchBottom: 41 });
  current = { ...current, ...change };
  assert.equal(wheelViewChange(wheel(0, 1, { shiftKey: true }), current, undefined, accumulator), null);
});

test("tiny Alt wheel deltas accumulate to one visible-note step", () => {
  const accumulator = { modifier: null, remainder: 0 } as import("../src/editor/wheelNavigation.ts").WheelPitchAccumulator;
  for (let i = 0; i < 29; i++) {
    assert.equal(wheelViewChange(wheel(0, -1, { altKey: true }), view, undefined, accumulator), null);
  }
  assert.deepEqual(wheelViewChange(wheel(0, -1, { altKey: true }), view, undefined, accumulator),
    { visibleNotes: 47, pitchBottom: 40 });
});

test("changing wheel modifiers or using horizontal pan clears fractional pitch carry", () => {
  const accumulator = { modifier: null, remainder: 0 } as import("../src/editor/wheelNavigation.ts").WheelPitchAccumulator;
  for (let i = 0; i < 20; i++) wheelViewChange(wheel(0, -1, { shiftKey: true }), view, undefined, accumulator);
  assert.equal(wheelViewChange(wheel(0, -1, { altKey: true }), view, undefined, accumulator), null);
  for (let i = 0; i < 20; i++) {
    assert.equal(wheelViewChange(wheel(0, -1, { shiftKey: true }), view, undefined, accumulator), null);
  }
  assert.ok(wheelViewChange(wheel(120, 0), view, undefined, accumulator)?.start !== undefined);
  for (let i = 0; i < 20; i++) {
    assert.equal(wheelViewChange(wheel(0, -1, { shiftKey: true }), view, undefined, accumulator), null);
  }
});
