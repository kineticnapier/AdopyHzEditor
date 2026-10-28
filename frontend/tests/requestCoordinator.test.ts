import assert from "node:assert/strict";
import test from "node:test";

import { AsyncActionGuard, enqueueAppliedTask, LatestRequestGate, SerialTaskQueue, runWithErrorFeedback } from "../src/api/requestCoordinator.ts";

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

test("failed editing reports an error and the serial queue recovers",async()=>{
  const queue=new SerialTaskQueue(),applied:number[]=[],errors:string[]=[];
  const failed=await runWithErrorFeedback(()=>queue.enqueue(async():Promise<number>=>{throw new Error("backend unavailable")}),value=>applied.push(value),message=>errors.push(message));
  assert.equal(failed,undefined);assert.deepEqual(applied,[]);assert.match(errors[0],/backend unavailable/);
  const succeeded=await runWithErrorFeedback(()=>queue.enqueue(async()=>42),value=>applied.push(value),message=>errors.push(message));
  assert.equal(succeeded,42);assert.deepEqual(applied,[42]);assert.equal(errors.length,1);
});

test("async action guard is single-flight and reusable",async()=>{
  const guard=new AsyncActionGuard();let release!:()=>void,calls=0;const barrier=new Promise<void>(resolve=>{release=resolve});
  const first=guard.run(async()=>{calls+=1;await barrier});await Promise.resolve();
  assert.equal(guard.isRunning,true);assert.equal(await guard.run(async()=>{calls+=1}),false);
  release();assert.equal(await first,true);assert.equal(guard.isRunning,false);
  assert.equal(await guard.run(async()=>{calls+=1}),true);assert.equal(calls,2);
});

test("inspector and canvas mutations apply in the same queue order", async () => {
  const queue = new SerialTaskQueue();
  const applied: string[][] = [];
  let releaseInspector!: (value: { notes: string[] }) => void;
  const inspector = enqueueAppliedTask(
    queue,
    () => new Promise<{ notes: string[] }>(resolve => { releaseInspector = resolve; }),
    result => { applied.push(result.notes); },
  );
  const canvas = enqueueAppliedTask(
    queue,
    async () => ({ notes: ["inspector", "canvas"] }),
    result => { applied.push(result.notes); },
  );
  await Promise.resolve();
  assert.deepEqual(applied, []);
  releaseInspector({ notes: ["inspector"] });
  await Promise.all([inspector, canvas]);
  assert.deepEqual(applied, [["inspector"], ["inspector", "canvas"]]);
});
