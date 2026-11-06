import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { wheelViewChange, type WheelInput } from "../src/editor/wheelNavigation.ts";
import { clampTimeViewChange } from "../src/editor/timelineNavigation.ts";
import { hasEffectiveViewChange } from "../src/editor/pitchViewport.ts";
import type { ViewState } from "../src/editor/bridge.ts";

const initial: ViewState = {
  mode: "spec", start: 20, windowSeconds: 12, pitchBottom: 40, visibleNotes: 48,
};
const wheel = (deltaY: number): WheelInput => ({
  deltaX: 0, deltaY, deltaMode: 0, shiftKey: false, altKey: false, ctrlKey: false,
});

test("wheel burst accumulates two fine scroll events before a React render", () => {
  let optimistic = initial;
  const changes: Partial<ViewState>[] = [];
  for (const delta of [1, 1]) {
    const change = wheelViewChange(wheel(delta), optimistic, undefined, undefined, 60);
    assert.ok(change);
    changes.push(change);
    optimistic = { ...optimistic, ...change };
  }
  assert.ok(Math.abs(optimistic.start - 20.016) < 1e-10);
  assert.ok(Math.abs((changes[1].start ?? 0) - 20.016) < 1e-10);
});

test("opposite wheel input must not be mistaken for a no-op against an older render", () => {
  const first = wheelViewChange(wheel(1), initial, undefined, undefined, 60);
  assert.ok(first);
  const latest = { ...initial, ...first };
  const reverse = wheelViewChange(wheel(-1), latest, undefined, undefined, 60);
  assert.ok(reverse);
  const normalized = clampTimeViewChange(latest, reverse, 60);
  assert.equal(hasEffectiveViewChange(latest, normalized), true);
  assert.equal(hasEffectiveViewChange(initial, normalized), false);
  assert.ok(Math.abs((reverse.start ?? 0) - initial.start) < 1e-10);
});

test("unrelated Canvas renders must not discard uncommitted wheel movement", () => {
  const canvas = readFileSync(new URL("../src/editor/EditorCanvas.tsx", import.meta.url), "utf8");
  // Only an actual new viewport prop may replace the optimistic wheel baseline.
  // A playback tick or hover/selection render can occur between two wheel events.
  const resetEffect = canvas.match(
    /useLayoutEffect\(\(\) => \{\s*wheelViewRef\.current = props\.view;\s*\},\s*(\[[^\]]*\])\s*\);/,
  );
  assert.ok(resetEffect, "wheel baseline must be synchronized by a dependency-scoped effect");
  assert.equal(resetEffect[1].replace(/\s/g, ""), "[props.view]");
});

test("Canvas connects the stable wheel listener to current view and callback refs", () => {
  const canvas = readFileSync(new URL("../src/editor/EditorCanvas.tsx", import.meta.url), "utf8");
  const app = readFileSync(new URL("../src/App.tsx", import.meta.url), "utf8");
  for (const part of [
    "const wheelViewRef = useRef(props.view)",
    "const wheelOnViewRef = useRef(props.onView)",
    "wheelOnViewRef.current = props.onView",
    "wheelDurationRef.current = props.playback.duration",
    "createCanvasWheelHandler({",
    "view: wheelViewRef,",
    "onView: wheelOnViewRef,",
    'canvas.addEventListener("wheel", handler, { passive: false })',
    'canvas.removeEventListener("wheel", handler)',
  ]) assert.ok(canvas.includes(part), `missing Canvas wiring: ${part}`);
  assert.ok(canvas.includes("return () => canvas.removeEventListener(\"wheel\", handler);\n  }, []);"));
  for (const part of [
    "const latestView = useRef(view)",
    "const currentView = latestView.current",
    "clampPitchViewChange(currentView, changes)",
    "hasEffectiveViewChange(currentView, normalized)",
    "latestView.current = next",
  ]) assert.ok(app.includes(part), `missing App view guard: ${part}`);
});
