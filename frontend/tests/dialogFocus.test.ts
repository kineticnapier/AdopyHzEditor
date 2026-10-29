import assert from "node:assert/strict";
import test from "node:test";
import { dialogTabDestination } from "../src/dialogs/dialogFocus.ts";

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
