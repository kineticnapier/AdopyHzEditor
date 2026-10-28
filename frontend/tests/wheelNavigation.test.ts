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
  assert.deepEqual(wheelViewChange(wheel(-10, 80), view), { start: 20.96 });
});

test("zero movement is ignored and line-mode horizontal scrolling is supported", () => {
  assert.equal(wheelViewChange(wheel(0, 0), view), null);
  assert.deepEqual(wheelViewChange(wheel(3, 0, { deltaMode: 1 }), view), { start: 20.96 });
});
