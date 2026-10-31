import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { dialogFocusableSelector, dialogTabDestination, isDialogTabbable } from "../src/dialogs/dialogFocus.ts";

const items = [{ focus() {} }, { focus() {} }, { focus() {} }];

test("forward Tab wraps from last to first", () => {
  assert.equal(dialogTabDestination(items, items[2], false), items[0]);
});

test("backward Tab wraps from first to last", () => {
  assert.equal(dialogTabDestination(items, items[0], true), items[2]);
});

test("interior Tab retains native focus order", () => {
  assert.equal(dialogTabDestination(items, items[1], false), null);
  assert.equal(dialogTabDestination(items, items[1], true), null);
});

test("focus that escaped the dialog is restored on Tab", () => {
  const outside = { focus() {} };
  assert.equal(dialogTabDestination(items, outside, false), items[0]);
  assert.equal(dialogTabDestination(items, outside, true), items[2]);
});

test("empty dialog has no target and hook can focus its container", () => {
  assert.equal(dialogTabDestination([], null, false), null);
  assert.equal(dialogTabDestination([], null, true), null);
});

test("dialog focus trap includes native summary and links in its tabbable query", () => {
  const selectors = dialogFocusableSelector.split(",");
  for (const selector of ["summary", "a[href]", "area[href]"]) {
    assert.ok(selectors.includes(selector), `missing focusable ${selector}`);
  }
  const hook = readFileSync(new URL("../src/dialogs/useDialogAccessibility.ts", import.meta.url), "utf8");
  assert.match(hook, /querySelectorAll<HTMLElement>\(dialogFocusableSelector\)/);
  assert.match(hook, /\.filter\(isDialogTabbable\)/);
});

test("Tab from the details summary can advance to the first advanced setting", () => {
  const close = { focus() {} }, summary = { focus() {} }, advanced = { focus() {} };
  const tabbable = [close, summary, advanced];
  assert.equal(dialogTabDestination(tabbable, summary, false), null);
  assert.equal(dialogTabDestination(tabbable, summary, true), null);
  assert.equal(dialogTabDestination(tabbable, advanced, false), close);
});

function fakeDialogControl(options: {
  disabled?: boolean;
  inert?: boolean;
  hidden?: boolean;
  tabIndex?: number;
} = {}): HTMLElement {
  return {
    getClientRects: () => options.hidden ? [] : [{}],
    tabIndex: options.tabIndex ?? 0,
    matches: (selector: string) => {
      assert.equal(selector, ":disabled");
      return !!options.disabled;
    },
    closest: (selector: string) => {
      assert.equal(selector, "[inert]");
      return options.inert ? {} : null;
    },
  } as unknown as HTMLElement;
}

test("dialog Tab trap skips controls disabled by their parent fieldset", () => {
  // HTML :disabled matches controls disabled by <fieldset disabled>, even
  // when the child input has no disabled attribute of its own.
  assert.equal(isDialogTabbable(fakeDialogControl()), true);
  assert.equal(isDialogTabbable(fakeDialogControl({ disabled: true })), false);
});

test("dialog Tab trap skips inert, hidden, and negative-tabIndex controls", () => {
  assert.equal(isDialogTabbable(fakeDialogControl({ inert: true })), false);
  assert.equal(isDialogTabbable(fakeDialogControl({ hidden: true })), false);
  assert.equal(isDialogTabbable(fakeDialogControl({ tabIndex: -1 })), false);
});
