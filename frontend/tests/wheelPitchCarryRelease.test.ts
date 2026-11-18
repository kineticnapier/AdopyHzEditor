import assert from "node:assert/strict";
import test from "node:test";
import { observeWheelPitchCarryRelease } from "../src/editor/canvasWheelHandler.ts";
import { wheelViewChange, type WheelPitchAccumulator } from "../src/editor/wheelNavigation.ts";
import type { ViewState } from "../src/editor/bridge.ts";

function fakeWindow() {
  const listeners = new Map<string, Set<(event: KeyboardEvent) => void>>();
  const target = {
    addEventListener(type: string, listener: (event: KeyboardEvent) => void) {
      if (!listeners.has(type)) listeners.set(type, new Set());
      listeners.get(type)!.add(listener);
    },
    removeEventListener(type: string, listener: (event: KeyboardEvent) => void) {
      listeners.get(type)?.delete(listener);
    },
  } as unknown as Pick<Window, "addEventListener" | "removeEventListener">;
  const fire = (type: string, key = "") => {
    for (const listener of listeners.get(type) ?? []) listener({ key } as KeyboardEvent);
  };
  return { target, fire };
}

test("Shift wheel remainder is cleared on Shift release, not unrelated key release", () => {
  const { target, fire } = fakeWindow();
  const carry = { current: { modifier: "shift", remainder: -.5 } as WheelPitchAccumulator };
  const stop = observeWheelPitchCarryRelease(target, carry);
  fire("keyup", "Control");
  assert.deepEqual(carry.current, { modifier: "shift", remainder: -.5 });
  fire("keyup", "Shift");
  assert.deepEqual(carry.current, { modifier: null, remainder: 0 });
  stop();
  carry.current = { modifier: "shift", remainder: -.5 };
  fire("keyup", "Shift");
  assert.deepEqual(carry.current, { modifier: "shift", remainder: -.5 });
});

test("Alt/AltGraph release and window blur discard the active pitch remainder", () => {
  const { target, fire } = fakeWindow();
  const carry = { current: { modifier: "alt", remainder: .75 } as WheelPitchAccumulator };
  const stop = observeWheelPitchCarryRelease(target, carry);
  fire("keyup", "Shift");
  assert.equal(carry.current.remainder, .75);
  fire("keyup", "AltGraph");
  assert.deepEqual(carry.current, { modifier: null, remainder: 0 });
  carry.current = { modifier: "alt", remainder: .5 };
  fire("keyup", "Alt");
  assert.deepEqual(carry.current, { modifier: null, remainder: 0 });
  carry.current = { modifier: "shift", remainder: -.25 };
  fire("blur");
  assert.deepEqual(carry.current, { modifier: null, remainder: 0 });
  stop();
});

test("separate fine Shift-wheel gestures do not combine fractional MIDI steps", () => {
  const { target, fire } = fakeWindow();
  const carry = { current: { modifier: null, remainder: 0 } as WheelPitchAccumulator };
  const stop = observeWheelPitchCarryRelease(target, carry);
  const view: ViewState = {
    mode: "spec", start: 20, windowSeconds: 12, pitchBottom: 40, visibleNotes: 48,
  };
  const event = {
    deltaX: 0, deltaY: 20, deltaMode: 0,
    shiftKey: true, altKey: false, ctrlKey: false,
  };
  assert.equal(wheelViewChange(event, view, undefined, carry.current, 60), null);
  assert.equal(carry.current.remainder, -.5);
  fire("keyup", "Shift");
  assert.equal(wheelViewChange(event, view, undefined, carry.current, 60), null);
  assert.equal(carry.current.remainder, -.5);
  stop();
});

test("hidden document resets pitch carry even without window blur; visible does not", () => {
  const { target } = fakeWindow();
  const listeners = new Set<() => void>();
  let visibilityState: DocumentVisibilityState = "visible";
  const documentTarget = {
    get visibilityState() { return visibilityState; },
    addEventListener(type: string, listener: () => void) {
      if (type === "visibilitychange") listeners.add(listener);
    },
    removeEventListener(type: string, listener: () => void) {
      if (type === "visibilitychange") listeners.delete(listener);
    },
  } as unknown as Pick<Document, "visibilityState" | "addEventListener" | "removeEventListener">;
  const fireVisibility = (state: DocumentVisibilityState) => {
    visibilityState = state;
    for (const listener of listeners) listener();
  };
  const carry = { current: { modifier: "shift", remainder: -.5 } as WheelPitchAccumulator };
  const stop = observeWheelPitchCarryRelease(target, carry, documentTarget);
  fireVisibility("visible");
  assert.deepEqual(carry.current, { modifier: "shift", remainder: -.5 });
  fireVisibility("hidden");
  assert.deepEqual(carry.current, { modifier: null, remainder: 0 });

  carry.current = { modifier: "alt", remainder: .75 };
  stop();
  assert.equal(listeners.size, 0);
  fireVisibility("hidden");
  assert.deepEqual(carry.current, { modifier: "alt", remainder: .75 });
});
