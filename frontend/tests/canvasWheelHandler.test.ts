import assert from "node:assert/strict";
import test from "node:test";
import type { ViewState } from "../src/editor/bridge.ts";
import { createCanvasWheelHandler } from "../src/editor/canvasWheelHandler.ts";
import type { WheelPitchAccumulator } from "../src/editor/wheelNavigation.ts";

const initial: ViewState = {
  mode: "spec", start: 20, windowSeconds: 12, pitchBottom: 40, visibleNotes: 48,
};

function setup() {
  const view = { current: { ...initial } };
  const pitchAccumulator = { current: { modifier: null, remainder: 0 } as WheelPitchAccumulator };
  const activePointerId = { current: null as number | null };
  const duration = { current: 60 };
  const first: Partial<ViewState>[] = [];
  const second: Partial<ViewState>[] = [];
  const onView = { current: (changes: Partial<ViewState>) => { first.push(changes); return Promise.resolve(); } };
  const canvas = { getBoundingClientRect: () => ({
    left: 0, bottom: 500, width: 800, height: 500,
  } as DOMRect) };
  const handler = createCanvasWheelHandler({
    canvas, view, pitchAccumulator, activePointerId, duration, onView,
  });
  let prevented = 0;
  const event = (deltaY: number, options: Partial<WheelEvent> = {}) => ({
    deltaX: 0, deltaY, deltaMode: 0,
    ctrlKey: false, altKey: false, shiftKey: false,
    clientX: 400, clientY: 250,
    preventDefault: () => { prevented++; },
    ...options,
  } as WheelEvent);
  return { handler, event, view, pitchAccumulator, activePointerId, duration, onView, first, second,
    getPrevented: () => prevented };
}

test("one mounted wheel listener retains fine-wheel movement across callback changes", () => {
  const s = setup();
  s.handler(s.event(1));
  s.onView.current = changes => { s.second.push(changes); return Promise.resolve(); };
  s.handler(s.event(1));
  assert.equal(s.first.length, 1);
  assert.equal(s.second.length, 1);
  assert.ok(Math.abs(s.view.current.start - 20.016) < 1e-10);
  assert.ok(Math.abs((s.second[0].start ?? NaN) - 20.016) < 1e-10);
  assert.equal(s.getPrevented(), 2);
});

test("wheel listener reads current duration without being rebound", () => {
  const s = setup();
  s.view.current = { ...initial, start: 8.99 };
  s.duration.current = 30;
  s.handler(s.event(1));
  s.duration.current = 21;
  s.handler(s.event(1));
  assert.ok(Math.abs(s.view.current.start - 9) < 1e-10);
  assert.ok(Math.abs((s.first[1].start ?? NaN) - 9) < 1e-10);
});

test("wheel during an owned pointer drag does not change the view or preserve pitch carry", () => {
  const s = setup();
  s.activePointerId.current = 7;
  s.pitchAccumulator.current = { modifier: "shift", remainder: .75 };
  s.handler(s.event(-1, { shiftKey: true }));
  assert.equal(s.first.length, 0);
  assert.deepEqual(s.view.current, initial);
  assert.deepEqual(s.pitchAccumulator.current, { modifier: null, remainder: 0 });
  assert.equal(s.getPrevented(), 1);
});
