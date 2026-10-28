import assert from "node:assert/strict";
import test from "node:test";
import { readFileSync } from "node:fs";

import { AsyncActionGuard, enqueueAppliedTask, enqueueRecoverableViewTask, enqueueStateTask, enqueueStateTaskAfterSettings, LatestRequestGate, SerialTaskQueue, runWithErrorFeedback } from "../src/api/requestCoordinator.ts";

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
    () => new Promise<void>((resolve) => { events.push("edit-start"); release = resolve; }),
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
    enqueueStateTask(queue, async (): Promise<number> => { throw new Error("load failed"); }, () => { applied = true; }),
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
  assert.match(app, /enqueueStateTaskAfterSettings\(\s*mutationQueue\.current,\s*flushPendingSettings,\s*guardedAction/);
  assert.match(app, /performStateAction\(\(\) => toolsApi\.apply_blank_workspace\(options\)\)/);
  assert.match(app, /enqueueStateTask\(\s*mutationQueue\.current,\s*\(\) => api\.save_project_dialog\(\)/);
  assert.match(dialogs, /await onApply\(value\)/);
});

test("pending settings finish before document state is requested or applied", async () => {
  const queue = new SerialTaskQueue();
  const events: string[] = [];
  let releaseSettings!: () => void;
  const transition = enqueueStateTaskAfterSettings(
    queue,
    () => new Promise<void>((resolve) => {
      events.push("settings-start");
      releaseSettings = () => { events.push("settings-finished"); resolve(); };
    }),
    async () => { events.push("load-document"); return "new document"; },
    () => { events.push("apply-document"); },
  );
  await Promise.resolve(); // The reserved queue slot starts in a microtask.
  assert.deepEqual(events, ["settings-start"]);
  releaseSettings();
  assert.equal(await transition, "new document");
  assert.deepEqual(events, ["settings-start", "settings-finished", "load-document", "apply-document"]);
});

test("document transitions reject concurrent settings edits", () => {
  const app = readFileSync(new URL("../src/App.tsx", import.meta.url), "utf8");
  assert.match(app, /if \(stateTransitionPending\.current > 0\) \{/);
  assert.match(app, /stateTransitionPending\.current \+= 1;/);
  assert.match(app, /stateTransitionPending\.current -= 1;/);
  assert.match(app, /enqueueStateTaskAfterSettings\(\s*mutationQueue\.current,\s*flushPendingSettings,/);
});

test("document switch keeps its queue position while settings are pending", async () => {
  const queue = new SerialTaskQueue();
  const events: string[] = [];
  let generation = 0;
  let releaseFirst!: () => void;
  let releaseSettings!: () => void;
  let settingsStarted!: () => void;
  const started = new Promise<void>((resolve) => { settingsStarted = resolve; });

  const first = enqueueAppliedTask(
    queue,
    () => new Promise<number>((resolve) => {
      events.push("edit-start");
      releaseFirst = () => resolve(1);
    }),
    () => { events.push("edit-applied"); },
    () => generation === 0,
  );
  await Promise.resolve();

  const transition = enqueueStateTaskAfterSettings(
    queue,
    () => {
      events.push("settings-start");
      settingsStarted();
      return new Promise<void>((resolve) => { releaseSettings = resolve; });
    },
    async () => { events.push("load-B"); return "B"; },
    () => { generation += 1; events.push("B-applied"); },
  );
  const stale = enqueueAppliedTask(
    queue,
    async () => { events.push("late-backend-call"); return 2; },
    () => { events.push("late-applied"); },
    () => generation === 0,
  );

  releaseFirst();
  await started;
  assert.deepEqual(events, ["edit-start", "edit-applied", "settings-start"]);
  releaseSettings();
  assert.deepEqual(await Promise.all([first, transition, stale]), [1, "B", undefined]);
  assert.deepEqual(events, ["edit-start", "edit-applied", "settings-start", "load-B", "B-applied"]);
});

test("settings failure releases the reserved document-switch queue slot", async () => {
  const queue = new SerialTaskQueue();
  let called = false;
  await assert.rejects(
    enqueueStateTaskAfterSettings(
      queue,
      async () => { throw new Error("settings rejected"); },
      async () => { called = true; return "B"; },
      () => { called = true; },
    ),
    /settings rejected/,
  );
  assert.equal(called, false);
  assert.equal(await queue.enqueue(async () => 7), 7);
});

test("current view failure invokes recovery and the view queue remains usable", async () => {
  const queue = new SerialTaskQueue();
  const recovered: string[] = [];
  await enqueueRecoverableViewTask(
    queue,
    async (): Promise<number> => { throw new Error("set_view failed"); },
    () => true,
    () => { throw new Error("failed request must not apply"); },
    async (error) => {
      recovered.push(String(error));
      recovered.push(String(await queue.enqueue(async () => 7)));
    },
  );
  assert.match(recovered[0], /set_view failed/);
  assert.deepEqual(recovered.slice(1), ["7"]);
});

test("stale view failure cannot recover over a newer request", async () => {
  const recovered: string[] = [];
  await enqueueRecoverableViewTask(
    new SerialTaskQueue(),
    async (): Promise<number> => { throw new Error("old request"); },
    () => false,
    () => { throw new Error("stale response must not apply"); },
    async () => { recovered.push("stale recovery"); },
  );
  assert.deepEqual(recovered, []);
});

test("view request applies only the current successful response", async () => {
  const queue = new SerialTaskQueue();
  const applied: number[] = [];
  await enqueueRecoverableViewTask(
    queue, async () => 12, () => true,
    (value) => { applied.push(value); },
    async () => { throw new Error("unexpected recovery"); },
  );
  await enqueueRecoverableViewTask(
    queue, async () => 13, () => false,
    (value) => { applied.push(value); },
    async () => { throw new Error("unexpected recovery"); },
  );
  assert.deepEqual(applied, [12]);
});

test("wheel and fit view share the recoverable request path", () => {
  const app = readFileSync(new URL("../src/App.tsx", import.meta.url), "utf8");
  assert.match(app, /await enqueueRecoverableViewTask\(\s*viewQueue\.current,/);
  assert.match(app, /applyViewAction\(\(\) => api\.set_view\(changes\), "表示範囲の変更"\)/);
  assert.match(app, /applyViewAction\(\(\) => api\.fit_view\(\), "全体表示"\)/);
  assert.match(app, /viewQueue\.current\.enqueue\(\(\) => api\.get_state\(\)\)/);
  assert.match(app, /generation === documentGeneration\.current/);
});

test("queued superseded follow request never writes the backend", async () => {
  const queue = new SerialTaskQueue();
  const gate = new LatestRequestGate();
  const calls: number[] = [];
  const applied: number[] = [];
  let release!: () => void;
  const blocker = queue.enqueue(() => new Promise<void>((resolve) => {
    release = resolve;
  }));
  await Promise.resolve();

  const old = gate.issue();
  const pending = enqueueRecoverableViewTask(
    queue,
    async () => { calls.push(1); return 1; },
    () => gate.isCurrent(old),
    (value) => { applied.push(value); },
    async () => { throw new Error("obsolete follow must not recover"); },
  );
  const newest = gate.issue();
  const latest = enqueueRecoverableViewTask(
    queue,
    async () => { calls.push(2); return 2; },
    () => gate.isCurrent(newest),
    (value) => { applied.push(value); },
    async () => { throw new Error("latest follow must not fail"); },
  );

  release();
  await Promise.all([blocker, pending, latest]);
  assert.deepEqual(calls, [2]);
  assert.deepEqual(applied, [2]);
});

test("playback follow shares manual view queue and error feedback", () => {
  const app = readFileSync(new URL("../src/App.tsx", import.meta.url), "utf8");
  assert.match(app, /void applyViewAction\(\(\) => api\.set_view\(\{ start: next \}\), "再生追従"\)/);
  assert.match(app, /stateTransitionPending\.current === 0/);
  assert.doesNotMatch(app, /void api\?\.set_view\(\{ start: next \}\)/);
});

test("document replacement waits for a started viewport write", async () => {
  const viewQueue = new SerialTaskQueue();
  const editQueue = new SerialTaskQueue();
  const gate = new LatestRequestGate();
  const events: string[] = [];
  let started!: () => void;
  let releaseView!: () => void;
  const viewStarted = new Promise<void>((resolve) => { started = resolve; });
  const oldRequest = gate.issue();
  const viewWrite = enqueueRecoverableViewTask(
    viewQueue,
    async () => {
      events.push("view-start");
      started();
      return new Promise<number>((resolve) => {
        releaseView = () => { events.push("view-end"); resolve(1); };
      });
    },
    () => gate.isCurrent(oldRequest),
    () => { events.push("stale-view-applied"); },
    async () => { events.push("stale-view-recovered"); },
  );
  await viewStarted;
  // This is done synchronously at the beginning of performStateAction().
  gate.invalidate();
  const transition = enqueueStateTaskAfterSettings(
    editQueue,
    async () => { events.push("settings-finished"); },
    async () => {
      await viewQueue.enqueue(async () => undefined);
      events.push("load-new");
      return "new";
    },
    () => { events.push("apply-new"); },
  );
  await Promise.resolve();
  assert.equal(events.includes("load-new"), false);
  releaseView();
  await Promise.all([viewWrite, transition]);
  assert.deepEqual(events, [
    "view-start", "settings-finished", "view-end", "load-new", "apply-new",
  ]);
});

test("document transition invalidates viewport work and blocks new view changes", () => {
  const app = readFileSync(new URL("../src/App.tsx", import.meta.url), "utf8");
  assert.match(app, /stateTransitionPending\.current \+= 1;\s*\/\/ Invalidate pending viewport writes[^\n]*\n\s*viewRequests\.current\.invalidate\(\)/);
  assert.match(app, /const guardedAction = async \(\) => \{\s*await viewQueue\.current\.enqueue\(async \(\) => undefined\);\s*return action\(\);/);
  assert.match(app, /async function updateView\(changes: Partial<ViewState>\) \{\s*if \(stateTransitionPending\.current > 0\)/);
  assert.match(app, /async function fitView\(\) \{\s*if \(stateTransitionPending\.current > 0\)/);
  assert.match(app, /if \(!api \|\| stateTransitionPending\.current > 0\) return;\s*const request = viewRequests\.current\.issue\(\)/);
  assert.match(app, /if \(stateTransitionPending\.current > 0 \|\| !followPlayback/);
});
