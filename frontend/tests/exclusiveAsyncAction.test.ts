import assert from "node:assert/strict";
import test from "node:test";
import { createExclusiveAsyncAction } from "../src/dialogs/exclusiveAsyncAction.ts";

test("concurrent clicks invoke the operation once", async () => {
  const run = createExclusiveAsyncAction();
  let resolve!: (value: string) => void;
  let calls = 0;
  const first = run(() => {
    calls += 1;
    return new Promise<string>(r => { resolve = r; });
  });
  const second = await run(async () => { calls += 1; return "unexpected"; });
  assert.equal(second, undefined);
  assert.equal(calls, 1);
  resolve("saved");
  assert.equal(await first, "saved");
});

test("another attempt is accepted after success", async () => {
  const run = createExclusiveAsyncAction();
  assert.equal(await run(async () => 1), 1);
  assert.equal(await run(async () => 2), 2);
});

test("rejection releases the lock for retry", async () => {
  const run = createExclusiveAsyncAction();
  await assert.rejects(run(async () => { throw new Error("disk full"); }), /disk full/);
  assert.equal(await run(async () => "retry ok"), "retry ok");
});

test("separate dialogs have independent guards", async () => {
  const a = createExclusiveAsyncAction(), b = createExclusiveAsyncAction();
  let release!: () => void;
  const waiting = a(() => new Promise<void>(r => { release = r; }));
  assert.equal(await b(async () => "independent"), "independent");
  release();
  await waiting;
});

test("harmonic insertion ignores duplicate requests while the mutation queue is pending", async () => {
  const insertOnce = createExclusiveAsyncAction();
  let resolve!: (value: { status: string } | undefined) => void;
  let insertCalls = 0;
  const queuedMutation = () => {
    insertCalls += 1;
    return new Promise<{ status: string } | undefined>(r => { resolve = r; });
  };
  const first = insertOnce(queuedMutation);
  assert.equal(await insertOnce(queuedMutation), undefined);
  assert.equal(insertCalls, 1);
  resolve({ status: "挿入しました" });
  assert.deepEqual(await first, { status: "挿入しました" });
  assert.deepEqual(await insertOnce(async () => ({ status: "再実行" })), { status: "再実行" });
});

test("harmonic insertion lock releases when a queued mutation becomes stale", async () => {
  const insertOnce = createExclusiveAsyncAction();
  assert.equal(await insertOnce(async () => undefined), undefined);
  assert.deepEqual(await insertOnce(async () => ({ status: "再試行" })), { status: "再試行" });
});
