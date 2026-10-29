import assert from "node:assert/strict";
import test from "node:test";
import { canvasEscapeAction, releaseCanvasPointerCapture } from "../src/editor/canvasInteraction.ts";

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
