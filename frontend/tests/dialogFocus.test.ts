import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { dialogFocusableSelector, dialogFocusRestorationTarget, dialogTabDestination, isDialogCompositionKey, isDialogTabbable, isTopmostDialog } from "../src/dialogs/dialogFocus.ts";

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
  ariaHidden?: boolean;
  hidden?: boolean;
  visibility?: "visible" | "hidden" | "collapse";
  tabIndex?: number;
} = {}): HTMLElement {
  return {
    getClientRects: () => options.hidden ? [] : [{}],
    ownerDocument: { defaultView: { getComputedStyle: () => ({ visibility: options.visibility ?? "visible" }) } },
    tabIndex: options.tabIndex ?? 0,
    matches: (selector: string) => {
      assert.equal(selector, ":disabled");
      return !!options.disabled;
    },
    closest: (selector: string) => {
      assert.equal(selector, "[inert], [aria-hidden='true']");
      return options.inert || options.ariaHidden ? {} : null;
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
  assert.equal(isDialogTabbable(fakeDialogControl({ ariaHidden: true })), false);
  assert.equal(isDialogTabbable(fakeDialogControl({ hidden: true })), false);
  assert.equal(isDialogTabbable(fakeDialogControl({ tabIndex: -1 })), false);
});


test("dialog Tab trap excludes visibility-hidden controls even with layout rectangles", () => {
  assert.equal(isDialogTabbable(fakeDialogControl({ visibility: "hidden" })), false);
  assert.equal(isDialogTabbable(fakeDialogControl({ visibility: "collapse" })), false);
  assert.equal(isDialogTabbable(fakeDialogControl({ visibility: "visible" })), true);
});


test("dialog Escape and Tab do not interrupt IME conversion", () => {
  // During Japanese conversion Escape cancels a candidate, not the dialog.
  assert.equal(isDialogCompositionKey({ isComposing: true, keyCode: 27 }), true);
  assert.equal(isDialogCompositionKey({ isComposing: true, keyCode: 9 }), true);
  // Windows IME compatibility: composition can be signalled only by keyCode 229.
  assert.equal(isDialogCompositionKey({ isComposing: false, keyCode: 229 }), true);
  assert.equal(isDialogCompositionKey({ isComposing: false, keyCode: 27 }), false);
  assert.equal(isDialogCompositionKey({ isComposing: false, keyCode: 9 }), false);
  const hook = readFileSync(new URL("../src/dialogs/useDialogAccessibility.ts", import.meta.url), "utf8");
  assert.match(hook, /event\.defaultPrevented \|\| isDialogCompositionKey\(event\)/);
});


test("only the frontmost modal handles keyboard events when dialogs overlap", () => {
  let dialogs: HTMLElement[] = [];
  const ownerDocument = {
    defaultView: { getComputedStyle: (dialog: HTMLElement) => ({ visibility: (dialog as any).testVisibility ?? "visible" }) },
    querySelectorAll: (selector: string) => {
      assert.equal(selector, '[role="dialog"][aria-modal="true"]');
      return dialogs;
    },
  };
  const modal = (options: { connected?: boolean; hidden?: boolean; inert?: boolean; ariaHidden?: boolean; visibility?: string } = {}) => ({
    isConnected: options.connected !== false,
    ownerDocument,
    getClientRects: () => options.hidden ? [] : [{}],
    closest: (selector: string) => {
      assert.equal(selector, "[inert], [aria-hidden='true']");
      return options.inert || options.ariaHidden ? {} : null;
    },
    testVisibility: options.visibility ?? "visible",
  }) as unknown as HTMLElement;
  const first = modal();
  const second = modal();
  dialogs = [first, second];
  assert.equal(isTopmostDialog(first), false);
  assert.equal(isTopmostDialog(second), true);
  assert.equal(isTopmostDialog(null), false);
  dialogs = [first];
  assert.equal(isTopmostDialog(first), true);
  assert.equal(isTopmostDialog(second), false);
  assert.equal(isTopmostDialog(modal({ connected: false })), false);
  // A later hidden, inert or aria-hidden dialog must not steal the key handler.
  for (const hidden of [
    modal({ hidden: true }),
    modal({ inert: true }),
    modal({ ariaHidden: true }),
    modal({ visibility: "hidden" }),
    modal({ visibility: "collapse" }),
    modal({ connected: false }),
  ]) {
    dialogs = [first, hidden];
    assert.equal(isTopmostDialog(first), true);
    assert.equal(isTopmostDialog(hidden), false);
  }
  dialogs = [first, second];

  const hook = readFileSync(new URL("../src/dialogs/useDialogAccessibility.ts", import.meta.url), "utf8");
  assert.match(hook, /event\.defaultPrevented \|\| isDialogCompositionKey\(event\) \|\| !isTopmostDialog\(dialog\)/);
  assert.match(hook, /if \(isTopmostDialog\(dialog\)\) \(focusable\(\)\[0\] \?\? dialog\)\.focus\(\)/);
});

test("dialog cleanup does not steal focus from a still-open modal", () => {
  let dialogs: HTMLElement[] = [];
  const doc = {
    activeElement: null as HTMLElement | null,
    defaultView: { getComputedStyle: () => ({ visibility: "visible" }) },
    querySelectorAll: (selector: string) => {
      assert.equal(selector, '[role="dialog"][aria-modal="true"]');
      return dialogs;
    },
  };
  const modal = (children: HTMLElement[]) => ({
    isConnected: true,
    ownerDocument: doc,
    getClientRects: () => [{}],
    closest: () => null,
    contains: (item: HTMLElement | null) => item !== null && children.includes(item),
    querySelectorAll: () => children,
  }) as unknown as HTMLElement;
  const control = () => ({
    isConnected: true,
    ownerDocument: doc,
    getClientRects: () => [{}],
    tabIndex: 0,
    matches: () => false,
    closest: () => null,
    focus() {},
  }) as unknown as HTMLElement;
  const previous = control(), foregroundControl = control(), outside = control();
  const lower = modal([previous]), upper = modal([foregroundControl]);
  dialogs = [lower, upper];
  doc.activeElement = foregroundControl;
  // The background dialog disappears while the user types in the foreground.
  assert.equal(dialogFocusRestorationTarget(previous, lower), null);
  // Closing the foreground restores the earlier focus in the remaining modal.
  doc.activeElement = outside;
  assert.equal(dialogFocusRestorationTarget(previous, upper), previous);
  // A previous element outside the remaining modal must not receive focus.
  assert.equal(dialogFocusRestorationTarget(outside, upper), previous);
  // Closing the final dialog restores the original application control.
  dialogs = [upper];
  assert.equal(dialogFocusRestorationTarget(outside, upper), outside);
  assert.equal(dialogFocusRestorationTarget(null, upper), null);

  const hook = readFileSync(new URL("../src/dialogs/useDialogAccessibility.ts", import.meta.url), "utf8");
  assert.match(hook, /dialogFocusRestorationTarget\(previous, dialog\)\?\.focus\(\)/);
});
