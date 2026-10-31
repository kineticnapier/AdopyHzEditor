import assert from "node:assert/strict";
import test from "node:test";
import { isInteractiveShortcutTarget, shouldDispatchEditorShortcut } from "../src/editor/shortcutTarget.ts";

const targetFor = (selectorToken: string): EventTarget => ({
  closest(selector: string) {
    return selector.split(",").includes(selectorToken) ? { tagName: "CONTROL" } : null;
  },
}) as unknown as EventTarget;

test("non-Element keydown targets do not throw or block canvas shortcuts", () => {
  for (const target of [null, {}, { closest: undefined }, { closest: null }, { closest: 5 }]) {
    assert.equal(isInteractiveShortcutTarget(target as EventTarget | null), false);
  }
  assert.equal(isInteractiveShortcutTarget(targetFor("canvas")), false);
});

test("text fields and native keyboard controls are protected", () => {
  for (const token of ["input", "select", "textarea", "[contenteditable='true']",
    "button", "a", "[role='menuitem']", "[role='menu']", "[role='dialog']",
    "[role='slider']", "[role='textbox']"]) {
    assert.equal(isInteractiveShortcutTarget(targetFor(token)), true, token);
  }
});

function keyEvent(target: EventTarget | null, key: string, overrides: Partial<KeyboardEvent> = {}) {
  return {
    target, key, ctrlKey: false, metaKey: false, repeat: false, defaultPrevented: false,
    ...overrides,
  } as Pick<KeyboardEvent, "target" | "key" | "ctrlKey" | "metaKey" | "repeat" | "defaultPrevented">;
}

test("Space and arrow keys on focused buttons and menus remain native", () => {
  assert.equal(shouldDispatchEditorShortcut(keyEvent(targetFor("button"), " "), false), false);
  assert.equal(shouldDispatchEditorShortcut(keyEvent(targetFor("button"), "ArrowUp"), false), false);
  assert.equal(shouldDispatchEditorShortcut(keyEvent(targetFor("[role='menuitem']"), "ArrowDown"), false), false);
  assert.equal(shouldDispatchEditorShortcut(keyEvent(targetFor("canvas"), " "), false), true);
});

test("Ctrl/Meta+S and F1 still work from fields, but disabled and handled events do not", () => {
  const input = targetFor("input");
  assert.equal(shouldDispatchEditorShortcut(keyEvent(input, "s", { ctrlKey: true }), false), true);
  assert.equal(shouldDispatchEditorShortcut(keyEvent(input, "s", { metaKey: true }), false), true);
  assert.equal(shouldDispatchEditorShortcut(keyEvent(input, "F1"), false), true);
  assert.equal(shouldDispatchEditorShortcut(keyEvent(input, "s", { ctrlKey: true }), true), false);
  assert.equal(shouldDispatchEditorShortcut(keyEvent(input, "s", { ctrlKey: true, defaultPrevented: true }), false), false);
  assert.equal(shouldDispatchEditorShortcut(keyEvent(targetFor("canvas"), "Delete", { repeat: true }), false), false);
});
