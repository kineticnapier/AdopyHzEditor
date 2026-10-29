import assert from "node:assert/strict";
import test from "node:test";
import { canvasEscapeAction, canStartCanvasGesture, isCanvasGesturePointer, releaseCanvasPointerCapture } from "../src/editor/canvasInteraction.ts";

test("Escape cancels a live canvas gesture without clearing the note selection", () => {
  assert.equal(canvasEscapeAction(true), "cancel-drag");
});

test("Escape clears selection only when no gesture is active", () => {
  assert.equal(canvasEscapeAction(false), "clear-selection");
});

test("cancel releases the active pointer capture exactly once", () => {
  const released: number[] = [];
  const canvas = {
    hasPointerCapture: (id: number) => id === 7 && released.length === 0,
    releasePointerCapture: (id: number) => { released.push(id); },
  };
  assert.equal(releaseCanvasPointerCapture(canvas, 7), true);
  assert.deepEqual(released, [7]);
  assert.equal(releaseCanvasPointerCapture(canvas, 7), false);
  assert.deepEqual(released, [7]);
});

test("cancel does not release a missing or foreign pointer", () => {
  const released: number[] = [];
  const canvas = {
    hasPointerCapture: (id: number) => id === 7,
    releasePointerCapture: (id: number) => { released.push(id); },
  };
  assert.equal(releaseCanvasPointerCapture(canvas, null), false);
  assert.equal(releaseCanvasPointerCapture(canvas, 9), false);
  assert.deepEqual(released, []);
});

test("first pointer owns the gesture until it is released", () => {
  assert.equal(canStartCanvasGesture(null), true);
  assert.equal(canStartCanvasGesture(7), false);
  assert.equal(isCanvasGesturePointer(7, 7), true);
  assert.equal(isCanvasGesturePointer(7, 9), false);
});

test("foreign pointer up/cancel cannot finish the current gesture", () => {
  let activePointerId: number | null = 7;
  let finishes = 0;
  const finish = (id: number) => {
    if (!isCanvasGesturePointer(activePointerId, id)) return;
    activePointerId = null;
    finishes++;
  };
  finish(9);
  assert.equal(activePointerId, 7);
  assert.equal(finishes, 0);
  finish(7);
  assert.equal(activePointerId, null);
  assert.equal(finishes, 1);
  assert.equal(isCanvasGesturePointer(null, 7), false);
  assert.equal(canStartCanvasGesture(activePointerId), true);
});
