import assert from "node:assert/strict";
import test from "node:test";

import { LatestRequestGate, SerialTaskQueue } from "../src/api/requestCoordinator.ts";

test("a late stale response cannot become current", () => {
  const gate = new LatestRequestGate();
  const first = gate.issue();
  const second = gate.issue();
  assert.equal(gate.isCurrent(second), true);
  assert.equal(gate.isCurrent(first), false);
});

test("invalidating a source rejects every in-flight response", () => {
  const gate = new LatestRequestGate();
  const request = gate.issue();
  gate.invalidate();
  assert.equal(gate.isCurrent(request), false);
});

test("serial queue preserves invocation order across deferred tasks", async () => {
  const queue = new SerialTaskQueue();
  const order: string[] = [];
  let releaseFirst!: () => void;
  const firstBarrier = new Promise<void>((resolve) => { releaseFirst = resolve; });
  const first = queue.enqueue(async () => {
    order.push("first-start");
    await firstBarrier;
    order.push("first-end");
    return 1;
  });
  const second = queue.enqueue(async () => {
    order.push("second");
    return 2;
  });
  await Promise.resolve();
  assert.deepEqual(order, ["first-start"]);
  releaseFirst();
  assert.deepEqual(await Promise.all([first, second]), [1, 2]);
  assert.deepEqual(order, ["first-start", "first-end", "second"]);
});
