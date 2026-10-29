import assert from "node:assert/strict";
import test from "node:test";
import { isNoteNavigationKey, reconcileKeyboardNote } from "../src/editor/noteKeyboardNavigation.ts";

const key = (name: string, mods: Partial<Pick<KeyboardEvent, "ctrlKey" | "metaKey" | "altKey" | "shiftKey">> = {}) => ({
  key: name, ctrlKey: false, metaKey: false, altKey: false, shiftKey: false, ...mods,
});

test("plain and Shift arrows navigate notes on the canvas", () => {
  for (const name of ["ArrowLeft", "ArrowRight"]) {
    assert.equal(isNoteNavigationKey(key(name)), true);
    assert.equal(isNoteNavigationKey(key(name, { shiftKey: true })), true);
  }
  assert.equal(isNoteNavigationKey(key("ArrowUp")), false);
});

test("Ctrl/Meta/Alt arrows are left to global shortcuts", () => {
  for (const name of ["ArrowLeft", "ArrowRight"]) {
    for (const mods of [
      { ctrlKey: true }, { ctrlKey: true, shiftKey: true },
      { metaKey: true }, { metaKey: true, shiftKey: true },
      { altKey: true }, { altKey: true, shiftKey: true },
    ]) assert.equal(isNoteNavigationKey(key(name, mods)), false);
  }
});

test("mouse or inspector selection becomes the next keyboard navigation origin", () => {
  assert.equal(reconcileKeyboardNote(0, [0], null, [3], 5, false), 3);
  assert.equal(reconcileKeyboardNote(3, [3], null, [1, 4], 5, false), 4);
});

test("Shift+arrow retains the active end even when selection indices are sorted", () => {
  assert.equal(reconcileKeyboardNote(1, [2, 3], [1, 2, 3], [1, 2, 3], 5, false), 1);
  assert.equal(reconcileKeyboardNote(1, [1, 2, 3], null, [1, 2, 3], 5, false), 1);
  assert.equal(reconcileKeyboardNote(2, [1, 2, 3], [1, 2, 3], [1, 2, 4], 5, false), 4);
});

test("clearing or replacing a document drops a stale keyboard cursor", () => {
  assert.equal(reconcileKeyboardNote(4, [4], null, [], 0, true), null);
  assert.equal(reconcileKeyboardNote(4, [4], [4], [4], 2, true), null);
  assert.equal(reconcileKeyboardNote(4, [4], null, [1], 2, true), 1);
  assert.equal(reconcileKeyboardNote(1, [1], null, [1], 2, true), 1);
});
