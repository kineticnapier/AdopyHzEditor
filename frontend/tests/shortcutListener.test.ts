import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { createEditorShortcutHandler, type ShortcutListenerState } from "../src/editor/shortcutListener.ts";

function keyEvent(key: string): KeyboardEvent {
  return {
    key, ctrlKey: false, metaKey: false, altKey: false, shiftKey: false,
    repeat: false, defaultPrevented: false, target: null,
    preventDefault() { this.defaultPrevented = true; },
  } as unknown as KeyboardEvent;
}

test("one shortcut handler uses the latest actions without re-registering", () => {
  const calls: string[] = [];
  let current = {
    api: {}, disabled: false, play: () => calls.push("old"),
  } as unknown as ShortcutListenerState;
  const handler = createEditorShortcutHandler(() => current);
  const first = keyEvent(" ");
  handler(first);
  assert.equal(first.defaultPrevented, true);
  assert.deepEqual(calls, ["old"]);

  current = { ...current, play: () => calls.push("new") };
  const second = keyEvent(" ");
  handler(second);
  assert.equal(second.defaultPrevented, true);
  assert.deepEqual(calls, ["old", "new"]);
});

test("a retained shortcut handler honors the newest disabled and API state", () => {
  const calls: string[] = [];
  let current = {
    api: {}, disabled: false, play: () => calls.push("play"),
  } as unknown as ShortcutListenerState;
  const handler = createEditorShortcutHandler(() => current);
  current = { ...current, disabled: true };
  const disabledEvent = keyEvent(" ");
  handler(disabledEvent);
  assert.equal(disabledEvent.defaultPrevented, false);
  current = { ...current, disabled: false, api: null };
  handler(keyEvent(" "));
  assert.deepEqual(calls, []);
  current = { ...current, api: {} as ShortcutListenerState["api"] };
  handler(keyEvent(" "));
  assert.deepEqual(calls, ["play"]);
});

test("the hook installs one window listener and updates its state in the layout phase", () => {
  const source = readFileSync(new URL("../src/editor/useEditorShortcuts.ts", import.meta.url), "utf8");
  assert.match(source, /useLayoutEffect\(\(\) => \{\s*latestArgs\.current = a;\s*\}, \[a\]\)/);
  assert.match(source, /createEditorShortcutHandler\(\(\) => latestArgs\.current\)/);
  assert.match(source, /window\.addEventListener\("keydown", handler\)/);
  assert.match(source, /window\.removeEventListener\("keydown", handler\)/);
  assert.match(source, /\}, \[\]\);/);
  assert.doesNotMatch(source, /\}, \[a\]\);\s*\}/);
});

test("repeated destructive editor chords are consumed without duplicate mutations", () => {
  const calls: string[] = [];
  const current = {
    api: {}, disabled: false,
    cut: () => calls.push("cut"),
    paste: () => calls.push("paste"),
    duplicate: () => calls.push("duplicate"),
    quantize: () => calls.push("quantize"),
    applyTargetAngle: () => calls.push("angle"),
    undo: () => calls.push("undo"),
    seek: (delta: number) => calls.push("seek:" + delta),
  } as unknown as ShortcutListenerState;
  const handler = createEditorShortcutHandler(() => current);
  const chords = [
    ["x", { ctrlKey: true }, "cut"],
    ["v", { metaKey: true }, "paste"],
    ["d", { ctrlKey: true }, "duplicate"],
    ["q", {}, "quantize"],
    ["a", { ctrlKey: true, altKey: true }, "angle"],
  ] as const;
  for (const [key, mods] of chords) {
    const repeated = Object.assign(keyEvent(key), mods, { repeat: true });
    handler(repeated);
    assert.equal(repeated.defaultPrevented, true, "repeat " + key);
  }
  assert.deepEqual(calls, []);
  for (const [key, mods] of chords) {
    const first = Object.assign(keyEvent(key), mods);
    handler(first);
    assert.equal(first.defaultPrevented, true, "first " + key);
  }
  assert.deepEqual(calls, ["cut", "paste", "duplicate", "quantize", "angle"]);
  const undo = Object.assign(keyEvent("z"), { ctrlKey: true, repeat: true });
  handler(undo);
  assert.equal(undo.defaultPrevented, true);
  assert.equal(calls.at(-1), "undo");
  const navigation = Object.assign(keyEvent("ArrowRight"), { repeat: true });
  handler(navigation);
  assert.equal(navigation.defaultPrevented, true);
  assert.equal(calls.at(-1), "seek:1");
});

test("repeated Ctrl+X in a focused native input is not intercepted", () => {
  const calls: string[] = [];
  const current = {
    api: {}, disabled: false, cut: () => calls.push("cut"),
  } as unknown as ShortcutListenerState;
  const handler = createEditorShortcutHandler(() => current);
  const input = { closest: () => ({}) } as unknown as EventTarget;
  const event = Object.assign(keyEvent("x"), { ctrlKey: true, repeat: true, target: input });
  handler(event);
  assert.equal(event.defaultPrevented, false);
  assert.deepEqual(calls, []);
});

test("repeated Ctrl/Meta+Shift+Arrow nudges are consumed without moving notes twice", () => {
  const calls: string[] = [];
  const current = {
    api: {}, disabled: false, selected: [2], nudgeSeconds: 0.25,
    move: (indices: number[], dx: number, dy: number) =>
      calls.push(`${indices.join(",")}:${dx},${dy}`),
  } as unknown as ShortcutListenerState;
  const handler = createEditorShortcutHandler(() => current);
  const keys = [
    ["ArrowLeft", "-0.25,0"],
    ["ArrowRight", "0.25,0"],
    ["ArrowUp", "0,1"],
    ["ArrowDown", "0,-1"],
  ] as const;
  for (const modifier of [{ ctrlKey: true }, { metaKey: true }]) {
    for (const [key] of keys) {
      const first = Object.assign(keyEvent(key), modifier, { shiftKey: true });
      handler(first);
      assert.equal(first.defaultPrevented, true, "first " + key);
      const repeated = Object.assign(keyEvent(key), modifier, { shiftKey: true, repeat: true });
      handler(repeated);
      assert.equal(repeated.defaultPrevented, true, "repeat " + key);
    }
  }
  assert.deepEqual(calls, [
    ...keys.map(([, delta]) => "2:" + delta),
    ...keys.map(([, delta]) => "2:" + delta),
  ]);
});

test("repeated navigation arrows remain available without Shift+Ctrl note movement", () => {
  const calls: string[] = [];
  const current = {
    api: {}, disabled: false,
    view: { mode: "spec", start: 0, windowSeconds: 12, pitchBottom: 24, visibleNotes: 60 },
    updateView: (changes: unknown) => calls.push("view:" + JSON.stringify(changes)),
    seek: (delta: number) => calls.push("seek:" + delta),
  } as unknown as ShortcutListenerState;
  const handler = createEditorShortcutHandler(() => current);
  const pitch = Object.assign(keyEvent("ArrowUp"), { ctrlKey: true, repeat: true });
  handler(pitch);
  const seek = Object.assign(keyEvent("ArrowRight"), { shiftKey: true, repeat: true });
  handler(seek);
  assert.equal(pitch.defaultPrevented, true);
  assert.equal(seek.defaultPrevented, true);
  assert.deepEqual(calls, ['view:{"pitchBottom":36}', "seek:5"]);
});
