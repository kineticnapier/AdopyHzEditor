import assert from "node:assert/strict";
import test from "node:test";
import { isNoteNavigationKey } from "../src/editor/noteKeyboardNavigation.ts";

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
