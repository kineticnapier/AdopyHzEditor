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

test("blank workspace apply is single-flight and prevents dismissal while pending", async () => {
  const applyOnce = createExclusiveAsyncAction();
  let release!: () => void;
  let applying = false, calls = 0, closes = 0;
  const apply = () => applyOnce(async () => {
    applying = true;
    calls += 1;
    try {
      await new Promise<void>(resolve => { release = resolve; });
    } finally {
      applying = false;
    }
  });
  const first = apply();
  assert.equal(await apply(), undefined);
  assert.equal(calls, 1);
  assert.equal(dismissUnlessBusy(applying, () => { closes += 1; }), false);
  assert.equal(closes, 0);
  release();
  await first;
  assert.equal(dismissUnlessBusy(applying, () => { closes += 1; }), true);
  assert.equal(closes, 1);
});

test("failed blank workspace apply restores dismissal and permits retry", async () => {
  const applyOnce = createExclusiveAsyncAction();
  let applying = false;
  await assert.rejects(
    applyOnce(async () => {
      applying = true;
      try { throw new Error("backend unavailable"); }
      finally { applying = false; }
    }),
    /backend unavailable/,
  );
  assert.equal(applying, false);
  let closes = 0;
  assert.equal(dismissUnlessBusy(applying, () => { closes += 1; }), true);
  assert.equal(closes, 1);
  assert.equal(await applyOnce(async () => "retry succeeded"), "retry succeeded");
});
