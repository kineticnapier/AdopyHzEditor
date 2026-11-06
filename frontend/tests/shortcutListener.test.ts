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
