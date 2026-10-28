import assert from "node:assert/strict";
import test from "node:test";
import { readFileSync } from "node:fs";

import { AsyncActionGuard, enqueueAppliedTask, enqueueStateTask, LatestRequestGate, SerialTaskQueue, runWithErrorFeedback } from "../src/api/requestCoordinator.ts";

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

test("queued old-document mutations never call the backend", async () => {
  const queue = new SerialTaskQueue();
  let release!: () => void;
  let documentGeneration = 0;
  let calls = 0;
  const applied: number[] = [];
  const blocker = queue.enqueue(
    () => new Promise<void>((resolve) => { release = resolve; }),
  );
  await Promise.resolve();
  const stale = enqueueAppliedTask(
    queue,
    async () => { calls += 1; return 42; },
    (value) => { applied.push(value); },
    () => documentGeneration === 0,
  );
  documentGeneration += 1;
  release();
  await blocker;
  assert.equal(await stale, undefined);
  assert.equal(calls, 0);
  assert.deepEqual(applied, []);
});

test("in-flight old-document responses never update the new document", async () => {
  const queue = new SerialTaskQueue();
  let release!: (value: number) => void;
  let documentGeneration = 0;
  const applied: number[] = [];
  const inFlight = enqueueAppliedTask(
    queue,
    () => new Promise<number>((resolve) => { release = resolve; }),
    (value) => { applied.push(value); },
    () => documentGeneration === 0,
  );
  await Promise.resolve();
  documentGeneration += 1;
  release(5);
  assert.equal(await inFlight, 5);
  assert.deepEqual(applied, []);
});

test("current-document mutations still execute and apply", async () => {
  const applied: number[] = [];
  const result = await enqueueAppliedTask(
    new SerialTaskQueue(),
    async () => 7,
    (value) => { applied.push(value); },
    () => true,
  );
  assert.equal(result, 7);
  assert.deepEqual(applied, [7]);
});

test("document transition waits for prior edits and rejects old queued edits", async () => {
  const queue = new SerialTaskQueue();
  const events: string[] = [];
  let generation = 0;
  let release!: () => void;
  const first = enqueueAppliedTask(
    queue,
    () => new Promise<void>((resolve) => {
      events.push("edit-start");
      release = resolve;
    }),
    () => { events.push("edit-applied"); },
    () => generation === 0,
  );
  await Promise.resolve();
  const switching = enqueueStateTask(
    queue,
    async () => { events.push("load-B"); return "B"; },
    () => { generation += 1; events.push("B-applied"); },
  );
  const stale = enqueueAppliedTask(
    queue,
    async () => { events.push("stale-backend-call"); return 42; },
    () => { events.push("stale-applied"); },
    () => generation === 0,
  );
  release();
  assert.equal(await switching, "B");
  assert.equal(await stale, undefined);
  await first;
  assert.deepEqual(events, ["edit-start", "edit-applied", "load-B", "B-applied"]);
});

test("failed document transition does not apply state and queue recovers", async () => {
  const queue = new SerialTaskQueue();
  let applied = false;
  await assert.rejects(
    enqueueStateTask(queue, async (): Promise<number> => {
      throw new Error("load failed");
    }, () => { applied = true; }),
    /load failed/,
  );
  assert.equal(applied, false);
  const next = await enqueueStateTask(queue, async () => 5, () => { applied = true; });
  assert.equal(next, 5);
  assert.equal(applied, true);
});

test("state actions, blank workspace and pending save use the same queue", () => {
  const app = readFileSync(new URL("../src/App.tsx", import.meta.url), "utf8");
  const dialogs = readFileSync(new URL("../src/dialogs/ToolDialogs.tsx", import.meta.url), "utf8");
  assert.match(app, /enqueueStateTask\(mutationQueue\.current, action/);
  assert.match(app, /performStateAction\(\(\) => toolsApi\.apply_blank_workspace\(options\)\)/);
  assert.match(app, /enqueueStateTask\(\s*mutationQueue\.current,\s*\(\) => api\.save_project_dialog\(\)/);
  assert.match(dialogs, /await onApply\(value\)/);
});
