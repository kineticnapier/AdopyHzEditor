import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { canvasEscapeAction, clearIdleCanvasSelection, canStartCanvasGesture, isCanvasGesturePointer, releaseCanvasPointerCapture, shouldSuppressCanvasArrowDuringPointerGesture, shouldSuppressCanvasNonArrowKeyDuringPointerGesture, shouldCancelCanvasGestureForResize, shouldCancelCanvasGestureForViewChange, observeCanvasPageExit, createTrailingReporter } from "../src/editor/canvasInteraction.ts";

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

test("arrow shortcuts are consumed while a pointer gesture owns the canvas", () => {
  for (const key of ["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown"]) {
    assert.equal(shouldSuppressCanvasArrowDuringPointerGesture(key, 7), true, key);
    assert.equal(shouldSuppressCanvasArrowDuringPointerGesture(key, null), false, key);
  }
  assert.equal(shouldSuppressCanvasArrowDuringPointerGesture("Escape", 7), false);
  assert.equal(shouldSuppressCanvasArrowDuringPointerGesture("Delete", 7), false);
});

test("canvas consumes gesture-time arrows before local and global shortcut handlers", () => {
  const source = readFileSync(new URL("../src/editor/EditorCanvas.tsx", import.meta.url), "utf8");
  const start = source.indexOf("function onCanvasKeyDown(");
  const end = source.indexOf("  useEffect(()=>{const canvas=", start);
  assert.ok(start >= 0 && end > start);
  const handler = source.slice(start, end);
  assert.match(handler, /if \(shouldSuppressCanvasArrowDuringPointerGesture\(event\.key, activePointerIdRef\.current\)\) \{\s*event\.preventDefault\(\);\s*return;\s*\}/);
  assert.ok(handler.indexOf("shouldSuppressCanvasArrowDuringPointerGesture") < handler.indexOf("isNoteNavigationKey(event)"));
});

test("context-menu deletion is blocked while another pointer owns a drag", () => {
  assert.equal(canStartCanvasGesture(null), true);
  assert.equal(canStartCanvasGesture(7), false);
  const source = readFileSync(new URL("../src/editor/EditorCanvas.tsx", import.meta.url), "utf8");
  const start = source.indexOf("async function onContextMenu(");
  const end = source.indexOf("function onCanvasKeyDown(", start);
  assert.ok(start >= 0 && end > start);
  const handler = source.slice(start, end);
  const prevent = handler.indexOf("event.preventDefault();");
  const guard = handler.indexOf("if (!canStartCanvasGesture(activePointerIdRef.current)) return;");
  const deletion = handler.indexOf("props.onDelete(");
  assert.ok(prevent >= 0 && guard > prevent && deletion > guard);
});

test("non-arrow editor shortcuts cannot change a gesture's captured note indices", () => {
  for (const key of ["x", "c", "v", "z", "y", "d", "a", "s", "o", "l", "i", "q", "Delete", "Backspace", "F1", "1", " "]) {
    assert.equal(shouldSuppressCanvasNonArrowKeyDuringPointerGesture(key, 7), true, key);
    assert.equal(shouldSuppressCanvasNonArrowKeyDuringPointerGesture(key, null), false, key);
  }
  for (const key of ["Escape", "Tab", "Control", "Shift", "Alt", "Meta", "ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown"]) {
    assert.equal(shouldSuppressCanvasNonArrowKeyDuringPointerGesture(key, 7), false, key);
  }
});

test("canvas blocks global editing shortcuts before note navigation while a pointer is held", () => {
  const source = readFileSync(new URL("../src/editor/EditorCanvas.tsx", import.meta.url), "utf8");
  const start = source.indexOf("function onCanvasKeyDown(");
  const end = source.indexOf("  useEffect(()=>{const canvas=", start);
  assert.ok(start >= 0 && end > start);
  const handler = source.slice(start, end);
  assert.match(handler, /if \(shouldSuppressCanvasNonArrowKeyDuringPointerGesture\(event\.key, activePointerIdRef\.current\)\) \{\s*event\.preventDefault\(\);\s*return;\s*\}/);
  assert.ok(handler.indexOf("shouldSuppressCanvasNonArrowKeyDuringPointerGesture") < handler.indexOf("isNoteNavigationKey(event)"));
  const shortcutTarget = readFileSync(new URL("../src/editor/shortcutTarget.ts", import.meta.url), "utf8");
  assert.match(shortcutTarget, /if \(event\.defaultPrevented \|\| disabled/);
});

test("focus loss cancels a pending canvas gesture before shortcuts can change notes", () => {
  const source = readFileSync(new URL("../src/editor/EditorCanvas.tsx", import.meta.url), "utf8");
  const start = source.indexOf("function onCanvasBlur(");
  const end = source.indexOf("async function onContextMenu(", start);
  assert.ok(start >= 0 && end > start);
  const handler = source.slice(start, end);
  assert.match(handler, /const pointerId = activePointerIdRef\.current;/);
  assert.match(handler, /if \(pointerId === null\) return;/);
  assert.match(handler, /cursorReporterRef\.current\.cancel\(\)/);
  const reset = handler.indexOf("activePointerIdRef.current = null;");
  const release = handler.indexOf("releaseCanvasPointerCapture(event.currentTarget, pointerId);");
  const cancel = handler.indexOf("setDrag(null);");
  assert.ok(reset >= 0 && release > reset && cancel > release);
  assert.match(source, /onBlur=\{onCanvasBlur\}/);
});

test("wheel input cannot move the viewport while a canvas pointer gesture is active", () => {
  const source = readFileSync(new URL("../src/editor/EditorCanvas.tsx", import.meta.url), "utf8");
  const start = source.indexOf("const handler=(event:WheelEvent)=>");
  const end = source.indexOf('canvas.addEventListener("wheel",handler', start);
  assert.ok(start >= 0 && end > start);
  const handler = source.slice(start, end);
  const prevent = handler.indexOf("event.preventDefault();");
  const guard = handler.indexOf("if(activePointerIdRef.current!==null)");
  const reset = handler.indexOf("wheelPitchAccumulatorRef.current={modifier:null,remainder:0};", guard);
  const stop = handler.indexOf("return;", reset);
  const compute = handler.indexOf("wheelViewChange(", stop);
  const dispatch = handler.indexOf("props.onView(changes)", compute);
  assert.ok(prevent >= 0 && guard > prevent && reset > guard && stop > reset);
  assert.ok(compute > stop && dispatch > compute);
});

test("window blur and page hiding cancel a canvas gesture, with cleanup", () => {
  const windowTarget = new EventTarget();
  const documentTarget = Object.assign(new EventTarget(), { visibilityState: "visible" });
  let cancellations = 0;
  const dispose = observeCanvasPageExit(windowTarget, documentTarget, () => { cancellations += 1; });
  documentTarget.dispatchEvent(new Event("visibilitychange"));
  assert.equal(cancellations, 0);
  windowTarget.dispatchEvent(new Event("blur"));
  assert.equal(cancellations, 1);
  documentTarget.visibilityState = "hidden";
  documentTarget.dispatchEvent(new Event("visibilitychange"));
  assert.equal(cancellations, 2);
  dispose();
  windowTarget.dispatchEvent(new Event("blur"));
  documentTarget.dispatchEvent(new Event("visibilitychange"));
  assert.equal(cancellations, 2);
});

test("canvas clears captured drag on page exit even if its own blur never fires", () => {
  const source = readFileSync(new URL("../src/editor/EditorCanvas.tsx", import.meta.url), "utf8");
  const start = source.indexOf("useEffect(() => observeCanvasPageExit(window, document,");
  const end = source.indexOf("}), []);", start);
  assert.ok(start >= 0 && end > start);
  const handler = source.slice(start, end);
  assert.match(handler, /if \(pointerId === null\) return;/);
  const reset = handler.indexOf("activePointerIdRef.current = null;");
  const release = handler.indexOf("releaseCanvasPointerCapture(canvasRef.current, pointerId);");
  const cancel = handler.indexOf("setDrag(null);");
  assert.ok(reset >= 0 && release > reset && cancel > release);
});

test("resizing a canvas cancels only a live gesture with changed dimensions", () => {
  const before = { width: 800, height: 500 };
  assert.equal(shouldCancelCanvasGestureForResize(null, before, { width: 900, height: 500 }), false);
  assert.equal(shouldCancelCanvasGestureForResize(7, before, { width: 800, height: 500 }), false);
  assert.equal(shouldCancelCanvasGestureForResize(7, before, { width: 900, height: 500 }), true);
  assert.equal(shouldCancelCanvasGestureForResize(7, before, { width: 800, height: 480 }), true);
});

test("ResizeObserver cancels the captured edit before applying a new canvas size", () => {
  const source = readFileSync(new URL("../src/editor/EditorCanvas.tsx", import.meta.url), "utf8");
  const start = source.indexOf("const observer = new ResizeObserver(");
  const end = source.indexOf("observer.observe(el);", start);
  assert.ok(start >= 0 && end > start);
  const handler = source.slice(start, end);
  assert.match(handler, /const previous = observedCanvasSizeRef\.current;/);
  assert.match(handler, /observedCanvasSizeRef\.current = next;/);
  assert.match(handler, /if \(shouldCancelCanvasGestureForResize\(activePointerIdRef\.current, previous, next\)\)/);
  const reset = handler.indexOf("activePointerIdRef.current = null;");
  const release = handler.indexOf("releaseCanvasPointerCapture(canvasRef.current, pointerId);");
  const cancel = handler.indexOf("setDrag(null);");
  const resize = handler.indexOf("setSize(next);");
  assert.ok(reset >= 0 && release > reset && cancel > release && resize > cancel);
});

test("a viewport mapping or mode change cancels a live canvas gesture", () => {
  const before = { start: 0, windowSeconds: 10, pitchBottom: 24, visibleNotes: 48, mode: "notes" };
  assert.equal(shouldCancelCanvasGestureForViewChange(null, before, { ...before, start: 1 }), false);
  assert.equal(shouldCancelCanvasGestureForViewChange(7, before, { ...before }), false);
  for (const change of [
    { start: 1 }, // Playback follow without a wheel event.
    { windowSeconds: 20 },
    { pitchBottom: 25 },
    { visibleNotes: 60 },
    { mode: "spectrum" },
  ]) {
    assert.equal(shouldCancelCanvasGestureForViewChange(7, before, { ...before, ...change }), true, JSON.stringify(change));
  }
});

test("Canvas releases the captured gesture synchronously when its viewport changes", () => {
  const source = readFileSync(new URL("../src/editor/EditorCanvas.tsx", import.meta.url), "utf8");
  assert.match(source, /import \\{ useEffect, useLayoutEffect,/);
  const start = source.indexOf("const observedCanvasViewRef = useRef(props.view);");
  const end = source.indexOf("}, [props.view]);", start);
  assert.ok(start >= 0 && end > start);
  const handler = source.slice(start, end);
  assert.match(handler, /useLayoutEffect\\(\\(\\) => \\{/);
  assert.match(handler, /shouldCancelCanvasGestureForViewChange\\(activePointerIdRef\\.current, previous, props\\.view\\)/);
  const updatePrevious = handler.indexOf("observedCanvasViewRef.current = props.view;");
  const guard = handler.indexOf("shouldCancelCanvasGestureForViewChange(");
  const reset = handler.indexOf("activePointerIdRef.current = null;");
  const release = handler.indexOf("releaseCanvasPointerCapture(canvasRef.current, pointerId);");
  const cancel = handler.indexOf("setDrag(null);");
  assert.ok(updatePrevious >= 0 && guard > updatePrevious && reset > guard && release > reset && cancel > release);
});
