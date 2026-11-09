import assert from "node:assert/strict";
import test from "node:test";
import { readFileSync } from "node:fs";
import { focusAdjacentMenu, isPlainMenuNavigationEvent, nextMenuId } from "../src/components/menuNavigation.ts";

const ids = ["file", "edit", "analyze", "tools", "options", "help"] as const;

test("arrow navigation uses the focused trigger rather than an older open menu", () => {
  assert.equal(nextMenuId(ids, "file", "edit", "ArrowRight"), "analyze");
  assert.equal(nextMenuId(ids, "file", "edit", "ArrowLeft"), "file");
});

test("arrow navigation from an open popup uses the active menu", () => {
  assert.equal(nextMenuId(ids, "analyze", null, "ArrowRight"), "tools");
  assert.equal(nextMenuId(ids, "analyze", null, "ArrowLeft"), "edit");
});

test("arrow navigation wraps and rejects an unknown trigger", () => {
  assert.equal(nextMenuId(ids, null, "help", "ArrowRight"), "file");
  assert.equal(nextMenuId(ids, null, "file", "ArrowLeft"), "help");
  assert.equal(nextMenuId(ids, null, "unknown", "ArrowRight"), null);
  assert.equal(nextMenuId(ids, null, null, "ArrowRight"), null);
});


test("menu navigation accepts plain keys but not already-consumed events", () => {
  assert.equal(isPlainMenuNavigationEvent({ defaultPrevented: false }), true);
  assert.equal(isPlainMenuNavigationEvent({ defaultPrevented: true }), false);
});

test("menu navigation leaves modified keys and IME conversion untouched", () => {
  for (const flag of ["ctrlKey", "metaKey", "altKey", "shiftKey", "isComposing"] as const) {
    assert.equal(isPlainMenuNavigationEvent({ defaultPrevented: false, [flag]: true }), false);
  }
  assert.equal(isPlainMenuNavigationEvent({ defaultPrevented: false, keyCode: 229 }), false);
});

test("trigger, popup, and menu-bar handlers all check native keyboard modifiers", () => {
  const source = readFileSync(new URL("../src/components/AppMenus.tsx", import.meta.url), "utf8");
  assert.equal(source.split("isPlainMenuNavigationEvent(event.nativeEvent)").length - 1, 3);
});


test("horizontal navigation from a popup focuses the first enabled item", () => {
  const focused: string[] = [];
  const root = { querySelector: (selector: string) => {
    if (selector === '[data-menu-id="edit"]') return { focus: () => focused.push("trigger") };
    if (selector === '[data-menu-popup="edit"] button:not(:disabled)') return { focus: () => focused.push("first item") };
    return null;
  } } as unknown as HTMLElement;
  focusAdjacentMenu(root, "edit", true);
  assert.deepEqual(focused, ["first item"]);
  focusAdjacentMenu(root, "edit", false);
  assert.deepEqual(focused, ["first item", "trigger"]);
});

test("horizontal navigation falls back to trigger if popup has no enabled item", () => {
  const focused: string[] = [];
  const root = { querySelector: (selector: string) =>
    selector === '[data-menu-id="help"]' ? { focus: () => focused.push("trigger") } : null,
  } as unknown as HTMLElement;
  focusAdjacentMenu(root, "help", true);
  focusAdjacentMenu(null, "help", true);
  assert.deepEqual(focused, ["trigger"]);
});

test("horizontal navigation connects popup identification and item focus", () => {
  const source = readFileSync(new URL("../src/components/AppMenus.tsx", import.meta.url), "utf8");
  assert.match(source, /data-menu-popup=\{id\}/);
  assert.match(source, /focusAdjacentMenu\(rootRef\.current,next,Boolean\(active && fromPopup\)\)/);
});
