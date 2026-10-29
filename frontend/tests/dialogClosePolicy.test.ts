import assert from "node:assert/strict";
import test from "node:test";
import { dismissUnlessBusy } from "../src/dialogs/dialogClosePolicy.ts";
import { createExclusiveAsyncAction } from "../src/dialogs/exclusiveAsyncAction.ts";

test("pending tool operation prevents closing the dialog", () => {
  let closes = 0;
  assert.equal(dismissUnlessBusy(true, () => { closes += 1; }), false);
  assert.equal(closes, 0);
});

test("idle tool dialog can close exactly once per dismissal", () => {
  let closes = 0;
  assert.equal(dismissUnlessBusy(false, () => { closes += 1; }), true);
  assert.equal(closes, 1);
});

test("dialog becomes dismissible after an asynchronous operation settles", async () => {
  let release!: () => void;
  const pending = new Promise<void>(resolve => { release = resolve; });
  const exclusive = createExclusiveAsyncAction();
  let busy = false;
  let closes = 0;
  const task = exclusive(async () => {
    busy = true;
    try { await pending; } finally { busy = false; }
  });
  assert.equal(dismissUnlessBusy(busy, () => { closes += 1; }), false);
  release();
  await task;
  assert.equal(dismissUnlessBusy(busy, () => { closes += 1; }), true);
  assert.equal(closes, 1);
});
