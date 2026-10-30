import assert from "node:assert/strict";
import test from "node:test";
import { isTextEditingTarget } from "../src/editor/shortcutTarget.ts";

test("keydown targets without Element.closest are not treated as text fields", () => {
  for (const target of [null, {}, { closest: undefined }, { closest: null }, { closest: 5 }]) {
    assert.equal(isTextEditingTarget(target as EventTarget | null), false);
  }
});

test("editable descendants are detected without suppressing unrelated shortcuts", () => {
  const selector = "input,select,textarea,[contenteditable='true']";
  const editingTarget = {
    closest(actual: string) { assert.equal(actual, selector); return { tagName: "INPUT" }; },
  } as unknown as EventTarget;
  const normalTarget = {
    closest(actual: string) { assert.equal(actual, selector); return null; },
  } as unknown as EventTarget;
  assert.equal(isTextEditingTarget(editingTarget), true);
  assert.equal(isTextEditingTarget(normalTarget), false);
});
