import assert from "node:assert/strict";
import test from "node:test";
import { readFileSync } from "node:fs";
import { canTransferDeferredMenuFocus, focusAdjacentMenu, isPlainMenuNavigationEvent, menuHoverFocusOrigin, nextMenuId, restoreMenuTriggerFocus } from "../src/components/menuNavigation.ts";

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

test("horizontal navigation falls back to trigger if an open popup has no enabled item", () => {
  const focused: string[] = [];
  const root = { querySelector: (selector: string) => {
    if (selector === '[data-menu-id="help"]') return { focus: () => focused.push("trigger") };
    if (selector === '[data-menu-popup="help"]') return {};
    return null;
  } } as unknown as HTMLElement;
  focusAdjacentMenu(root, "help", true, true);
  focusAdjacentMenu(null, "help", true, true);
  assert.deepEqual(focused, ["trigger"]);
});

test("deferred navigation never focuses a trigger after its popup has closed", () => {
  const focused: string[] = [];
  const root = { querySelector: (selector: string) =>
    selector === '[data-menu-id="edit"]' ? { focus: () => focused.push("trigger") } : null,
  } as unknown as HTMLElement;
  focusAdjacentMenu(root, "edit", true, true);
  focusAdjacentMenu(root, "edit", false, true);
  assert.deepEqual(focused, []);
  // With no open menu, moving between triggers remains valid.
  focusAdjacentMenu(root, "edit", false, false);
  assert.deepEqual(focused, ["trigger"]);
});

test("deferred navigation focuses an open menu when the popup still exists", () => {
  const focused: string[] = [];
  const root = { querySelector: (selector: string) => {
    if (selector === '[data-menu-popup="edit"]') return {};
    if (selector === '[data-menu-id="edit"]') return { focus: () => focused.push("trigger") };
    if (selector === '[data-menu-popup="edit"] button:not(:disabled)') return { focus: () => focused.push("first item") };
    return null;
  } } as unknown as HTMLElement;
  focusAdjacentMenu(root, "edit", true, true);
  focusAdjacentMenu(root, "edit", false, true);
  assert.deepEqual(focused, ["first item", "trigger"]);
});

test("horizontal navigation connects popup identification and item focus", () => {
  const source = readFileSync(new URL("../src/components/AppMenus.tsx", import.meta.url), "utf8");
  assert.match(source, /data-menu-popup=\{id\}/);
  assert.match(source, /focusAdjacentMenu\(rootRef\.current,next,Boolean\(active && fromPopup\),Boolean\(active\)\)/);
});


test("menu closing leaves newly focused dialog controls alone", () => {
  const focused: string[] = [];
  const root = { querySelector: () => ({ focus: () => focused.push("menu") }) } as unknown as HTMLElement;
  const body = { isConnected: true } as Element;
  const html = { isConnected: true } as Element;
  const dialogInput = { isConnected: true } as Element;
  restoreMenuTriggerFocus(root, "help", dialogInput, body, html);
  assert.deepEqual(focused, []);
});

test("menu closing restores focus when the old popup is gone", () => {
  const focused: string[] = [];
  const root = { querySelector: () => ({ focus: () => focused.push("menu") }) } as unknown as HTMLElement;
  const body = { isConnected: true } as Element;
  const html = { isConnected: true } as Element;
  const detachedItem = { isConnected: false } as Element;
  restoreMenuTriggerFocus(root, "file", body, body, html);
  restoreMenuTriggerFocus(root, "file", html, body, html);
  restoreMenuTriggerFocus(root, "file", detachedItem, body, html);
  assert.deepEqual(focused, ["menu", "menu", "menu"]);
});

test("menu close and Escape both use guarded focus restoration", () => {
  const source = readFileSync(new URL("../src/components/AppMenus.tsx", import.meta.url), "utf8");
  assert.match(source, /const focusTrigger=.*restoreMenuTriggerFocus/);
  assert.match(source, /consumeMenuEscape\(e,active,id=>\{setActive\(null\);focusTrigger\(id\)\}\)/);
  assert.match(source, /const close=\(\)=>\{const id=active;setActive\(null\);if\(id\)focusTrigger\(id\)\}/);
});

test("hovering an open menu transfers focus only from its active popup or trigger", () => {
  const focused = (matchingSelector: string | null) => ({
    closest: (selector: string) => selector === matchingSelector ? {} : null,
  }) as unknown as Pick<Element, "closest">;
  assert.equal(menuHoverFocusOrigin("file", focused('[data-menu-popup="file"]')), "popup");
  assert.equal(menuHoverFocusOrigin("file", focused('[data-menu-id="file"]')), "trigger");
  assert.equal(menuHoverFocusOrigin("file", focused('[data-menu-popup="edit"]')), null);
  assert.equal(menuHoverFocusOrigin("file", focused(null)), null);
  assert.equal(menuHoverFocusOrigin("file", null), null);
});

test("hovered menu preserves the focus kind and ignores closed destinations", () => {
  const focused: string[] = [];
  let open = true;
  const root = { querySelector: (selector: string) => {
    if (selector === '[data-menu-popup="edit"]') return open ? {} : null;
    if (selector === '[data-menu-id="edit"]') return { focus: () => focused.push("trigger") };
    if (selector === '[data-menu-popup="edit"] button:not(:disabled)') return { focus: () => focused.push("item") };
    return null;
  } } as unknown as HTMLElement;
  focusAdjacentMenu(root, "edit", true, true);
  focusAdjacentMenu(root, "edit", false, true);
  open = false;
  focusAdjacentMenu(root, "edit", true, true);
  assert.deepEqual(focused, ["item", "trigger"]);
});

test("hover focus transfer is wired only for an already open different menu", () => {
  const source = readFileSync(new URL("../src/components/AppMenus.tsx", import.meta.url), "utf8");
  assert.match(source, /if\(active===null\|\|open\)return/);
  assert.match(source, /menuHoverFocusOrigin\(active,focusedBeforeSwitch\)/);
  assert.match(source, /if\(origin\)window\.requestAnimationFrame\(\(\)=>\{/);
  assert.match(source, /focusAdjacentMenu\(root,id,origin==="popup",true\)/);
});

test("deferred menu focus never overrides a newly focused connected control", () => {
  const body = { isConnected: true } as Element;
  const html = { isConnected: true } as Element;
  const original = { isConnected: true } as Element;
  const newControl = { isConnected: true } as Element;
  assert.equal(canTransferDeferredMenuFocus(original, newControl, body, html), false);
});

test("deferred menu focus proceeds only while focus remains unclaimed", () => {
  const body = { isConnected: true } as Element;
  const html = { isConnected: true } as Element;
  const original = { isConnected: true } as Element;
  const detached = { isConnected: false } as Element;
  for (const current of [original, body, html, detached, null]) {
    assert.equal(canTransferDeferredMenuFocus(original, current, body, html), true);
  }
});

test("hover and horizontal menu moves both guard deferred focus", () => {
  const source = readFileSync(new URL("../src/components/AppMenus.tsx", import.meta.url), "utf8");
  assert.equal(source.split("canTransferDeferredMenuFocus(").length - 1, 2);
});
