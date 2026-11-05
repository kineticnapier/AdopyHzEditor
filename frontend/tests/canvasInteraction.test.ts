import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { canvasEscapeAction, clearIdleCanvasSelection, canStartCanvasGesture, isCanvasGesturePointer, releaseCanvasPointerCapture, createTrailingReporter } from "../src/editor/canvasInteraction.ts";

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

test("idle Escape clears Track before Note selection", () => {
  const calls: string[] = [];
  clearIdleCanvasSelection(() => calls.push("tracks"), () => calls.push("notes"));
  assert.deepEqual(calls, ["tracks", "notes"]);
});

test("canvas Escape wires Track invalidation into the idle path only", () => {
  const source = readFileSync(new URL("../src/editor/EditorCanvas.tsx", import.meta.url), "utf8");
  const start = source.indexOf("function onCanvasKeyDown(");
  const end = source.indexOf("  useEffect(()=>{const canvas=", start);
  assert.ok(start >= 0 && end > start);
  const handler = source.slice(start, end);
  assert.match(handler, /if \(event\.key === "Escape" && !event\.ctrlKey && !event\.metaKey && !event\.altKey && !event\.shiftKey\) \{/);
  assert.match(handler, /if \(canvasEscapeAction\(drag !== null\) === "cancel-drag"\) \{[\s\S]*?return;\s*\}/);
  assert.match(handler, /clearIdleCanvasSelection\(clearTrackSelection, \(\) => props\.onSelect\(\[\]\)\)/);
  assert.equal(handler.match(/clearIdleCanvasSelection\(/g)?.length, 1);
});

test("cursor reporting delivers the final position after the throttle interval", () => {
  let now = 100, nextId = 0;
  const scheduled = new Map<number, { callback: () => void; delay: number }>();
  const emitted: string[] = [];
  const reporter = createTrailingReporter<string>(
    50,
    () => now,
    (callback, delay) => {
      const id = ++nextId;
      scheduled.set(id, { callback, delay });
      return id;
    },
    id => { scheduled.delete(id); },
  );
  reporter.report("first", value => emitted.push(value));
  assert.deepEqual(emitted, ["first"]);
  now = 120;
  reporter.report("intermediate", value => emitted.push(value));
  now = 130;
  reporter.report("final", value => emitted.push(value));
  assert.deepEqual(emitted, ["first"]);
  assert.equal(scheduled.size, 1);
  const [id, timer] = [...scheduled][0];
  assert.equal(timer.delay, 30);
  now = 150;
  scheduled.delete(id);
  timer.callback();
  assert.deepEqual(emitted, ["first", "final"]);
  assert.equal(scheduled.size, 0);
});

test("leaving the canvas cancels pending cursor and Track hover reports", () => {
  let now = 100, nextId = 0;
  const scheduled = new Map<number, () => void>();
  const emitted: string[] = [];
  const reporter = createTrailingReporter<string>(
    50, () => now,
    callback => { const id = ++nextId; scheduled.set(id, callback); return id; },
    id => { scheduled.delete(id); },
  );
  reporter.report("initial", value => emitted.push(value));
  now = 110;
  reporter.report("stale", value => emitted.push(value));
  assert.equal(scheduled.size, 1);
  reporter.cancel();
  assert.equal(scheduled.size, 0);
  now = 200;
  reporter.report("new", value => emitted.push(value));
  assert.deepEqual(emitted, ["initial", "new"]);
});

test("canvas wires trailing reports and cancels them on pointer leave and unmount", () => {
  const source = readFileSync(new URL("../src/editor/EditorCanvas.tsx", import.meta.url), "utf8");
  assert.match(source, /cursorReporterRef\.current\.report\(/);
  assert.match(source, /onPointerLeave=\{\(\)=>\{cursorReporterRef\.current\.cancel\(\);props\.onTrackHover\?\.\(null\)\}\}/);
  assert.match(source, /useEffect\(\(\) => \(\) => cursorReporterRef\.current\.cancel\(\), \[\]\)/);
});

test("cancel resets the throttle so reentering the canvas reports immediately", () => {
  let now = 100, nextId = 0;
  const scheduled = new Map<number, () => void>();
  const emitted: string[] = [];
  const reporter = createTrailingReporter<string>(
    50, () => now,
    callback => { const id = ++nextId; scheduled.set(id, callback); return id; },
    id => { scheduled.delete(id); },
  );
  reporter.report("initial", value => emitted.push(value));
  now = 110;
  reporter.report("old pending", value => emitted.push(value));
  assert.equal(scheduled.size, 1);
  reporter.cancel();
  now = 115;
  reporter.report("new session", value => emitted.push(value));
  assert.deepEqual(emitted, ["initial", "new session"]);
  assert.equal(scheduled.size, 0);
});

test("canvas clears pending and displayed Track hover when view or document data changes", () => {
  const source = readFileSync(new URL("../src/editor/EditorCanvas.tsx", import.meta.url), "utf8");
  const start = source.indexOf("// View/data changes invalidate hover coordinates");
  const end = source.indexOf("const wheelPitchAccumulatorRef", start);
  assert.ok(start >= 0 && end > start);
  const effect = source.slice(start, end);
  assert.match(effect, /cursorReporterRef\.current\.cancel\(\)/);
  assert.match(effect, /props\.onTrackHover\?\.\(null\)/);
  assert.match(effect, /\[props\.notes, props\.frequencyTracks, props\.view, size\]/);
  assert.ok(effect.indexOf("cursorReporterRef.current.cancel()") < effect.indexOf("props.onTrackHover?.(null)"));
});

test("App connects Canvas Track hover to the displayed hover state", () => {
  const source = readFileSync(new URL("../src/App.tsx", import.meta.url), "utf8");
  assert.match(source, /onTrackHover=\{setHoveredTrack\}/);
});

test("stale timer callbacks cannot flush a new pointer session", () => {
  let now = 100, nextId = 0;
  const scheduled = new Map<number, () => void>();
  const emitted: string[] = [];
  const reporter = createTrailingReporter<string>(
    50, () => now,
    callback => { const id = ++nextId; scheduled.set(id, callback); return id; },
    id => { scheduled.delete(id); },
  );
  const emit = (value: string) => emitted.push(value);
  reporter.report("first", emit);
  now = 110;
  reporter.report("old pending", emit);
  const staleCallback = scheduled.get(1);
  assert.ok(staleCallback);
  reporter.cancel();
  now = 120;
  reporter.report("new first", emit);
  now = 125;
  reporter.report("new pending", emit);
  staleCallback();
  assert.deepEqual(emitted, ["first", "new first"]);
  const currentCallback = scheduled.get(2);
  assert.ok(currentCallback);
  now = 170;
  currentCallback();
  staleCallback();
  assert.deepEqual(emitted, ["first", "new first", "new pending"]);
});

test("superseded timer callbacks cannot emit a later pending position early", () => {
  let now = 100, nextId = 0;
  const scheduled = new Map<number, () => void>();
  const emitted: string[] = [];
  const reporter = createTrailingReporter<string>(
    50, () => now,
    callback => { const id = ++nextId; scheduled.set(id, callback); return id; },
    id => { scheduled.delete(id); },
  );
  const emit = (value: string) => emitted.push(value);
  reporter.report("first", emit);
  now = 110;
  reporter.report("old pending", emit);
  const supersededCallback = scheduled.get(1);
  assert.ok(supersededCallback);
  now = 150;
  reporter.report("immediate", emit);
  now = 155;
  reporter.report("new pending", emit);
  supersededCallback();
  assert.deepEqual(emitted, ["first", "immediate"]);
  const currentCallback = scheduled.get(2);
  assert.ok(currentCallback);
  now = 200;
  currentCallback();
  assert.deepEqual(emitted, ["first", "immediate", "new pending"]);
});

test("pointer down clears the displayed Track hover before starting a gesture", () => {
  const source = readFileSync(new URL("../src/editor/EditorCanvas.tsx", import.meta.url), "utf8");
  const start = source.indexOf("function onPointerDown(");
  const end = source.indexOf("function onPointerMove(", start);
  assert.ok(start >= 0 && end > start);
  const handler = source.slice(start, end);
  const cancel = handler.indexOf("cursorReporterRef.current.cancel();");
  const clear = handler.indexOf("props.onTrackHover?.(null);", cancel);
  const capture = handler.indexOf("setPointerCapture(", cancel);
  assert.ok(cancel >= 0 && clear > cancel && capture > clear);
});
