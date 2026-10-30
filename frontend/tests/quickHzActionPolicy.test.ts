import assert from "node:assert/strict";
import test from "node:test";
import { readFileSync } from "node:fs";
import { createExclusiveAsyncAction } from "../src/dialogs/exclusiveAsyncAction.ts";
import { quickHzActionPolicy } from "../src/dialogs/quickHzActionPolicy.ts";
import { runQuickHzOutputAction } from "../src/dialogs/quickHzOutputActions.ts";

test("pending chart selection or append locks every setting and action", () => {
  assert.deepEqual(quickHzActionPolicy(true, true, true), {
    canEdit: false,
    canChooseChart: false,
    canAppend: false,
    canOutput: false,
    canClose: false,
  });
});

test("ready preview allows editing, output and chart append", () => {
  assert.deepEqual(quickHzActionPolicy(false, true, true), {
    canEdit: true,
    canChooseChart: true,
    canAppend: true,
    canOutput: true,
    canClose: true,
  });
});

test("stale preview cannot be appended or exported", () => {
  const policy = quickHzActionPolicy(false, true, false);
  assert.equal(policy.canEdit, true);
  assert.equal(policy.canAppend, false);
  assert.equal(policy.canOutput, false);
});

test("a valid preview without a chosen chart can still be copied", () => {
  const policy = quickHzActionPolicy(false, false, true);
  assert.equal(policy.canAppend, false);
  assert.equal(policy.canOutput, true);
  assert.equal(policy.canChooseChart, true);
});

test("a pending chart picker cannot race with an append and allows retry", async () => {
  const run = createExclusiveAsyncAction();
  let releasePicker!: () => void;
  let selectedChart = "original.adofai";
  const written: string[] = [];
  const choosing = run(async () => {
    await new Promise<void>(resolve => { releasePicker = resolve; });
    selectedChart = "replacement.adofai";
  });
  const rejectedAppend = await run(async () => { written.push(selectedChart); });
  assert.equal(rejectedAppend, undefined);
  assert.deepEqual(written, []);
  releasePicker();
  await choosing;
  await run(async () => { written.push(selectedChart); });
  assert.deepEqual(written, ["replacement.adofai"]);
});

test("a pending append cannot be superseded by a late chart selection", async () => {
  const run = createExclusiveAsyncAction();
  let finishAppend!: () => void;
  let pickerCalls = 0;
  const append = run(() => new Promise<void>(resolve => { finishAppend = resolve; }));
  const ignoredPicker = await run(async () => { pickerCalls += 1; });
  assert.equal(ignoredPicker, undefined);
  assert.equal(pickerCalls, 0);
  finishAppend();
  await append;
  await run(async () => { pickerCalls += 1; });
  assert.equal(pickerCalls, 1);
});

test("Quick Hz connects picker and append to one guard and locks the dialog", () => {
  const source = readFileSync(new URL("../src/dialogs/ToolDialogs.tsx", import.meta.url), "utf8");
  const start = source.indexOf("export function QuickHzDialog");
  const end = source.indexOf("export function HarmonicDiagramDialog");
  assert.ok(start >= 0 && end > start);
  const dialog = source.slice(start, end);
  assert.match(dialog, /const busy = appending \\|\\| choosing \\|\\| outputting !== null/);
  assert.match(dialog, /quickHzActionPolicy\(busy, Boolean\(chart\), resultCurrent\)/);
  assert.match(dialog, /async function chooseChart\(\)\s*\{[\s\S]*?await appendOnce\.current\(async \(\) => \{/);
  assert.match(dialog, /async function append\(\)\s*\{[\s\S]*?await appendOnce\.current\(async \(\) => \{/);
  assert.match(dialog, /<Modal title="Quick Hz ツール" onClose=\{onClose\} wide locked=\{busy\}>/);
  assert.match(dialog, /setChoosing\(false\)/);
});

test("a pending Quick Hz copy excludes save and chart actions, then allows retry", async () => {
  const run = createExclusiveAsyncAction();
  const calls: string[] = [];
  let releaseCopy!: () => void;
  const copy = run(async () => {
    await runQuickHzOutputAction(
      "コピー",
      () => new Promise<void>(resolve => { releaseCopy = resolve; }),
      () => calls.push("copied"),
      message => calls.push(message),
    );
  });
  assert.equal(await run(async () => { calls.push("saved"); }), undefined);
  assert.equal(await run(async () => { calls.push("picked"); }), undefined);
  assert.deepEqual(calls, []);
  releaseCopy();
  await copy;
  assert.deepEqual(calls, ["copied"]);
  await run(async () => { calls.push("saved"); });
  assert.deepEqual(calls, ["copied", "saved"]);
});

test("Quick Hz failed text save releases the shared lock for another action", async () => {
  const run = createExclusiveAsyncAction();
  const calls: string[] = [];
  await run(async () => {
    await runQuickHzOutputAction(
      "テキスト保存",
      async () => { throw new Error("disk full"); },
      () => calls.push("saved"),
      message => calls.push(message),
    );
  });
  assert.deepEqual(calls, ["テキスト保存に失敗しました: Error: disk full"]);
  await run(async () => { calls.push("retry"); });
  assert.deepEqual(calls, ["テキスト保存に失敗しました: Error: disk full", "retry"]);
});

test("Quick Hz output handlers share the chart lock and keep the modal busy", () => {
  const source = readFileSync(new URL("../src/dialogs/ToolDialogs.tsx", import.meta.url), "utf8");
  const start = source.indexOf("export function QuickHzDialog");
  const end = source.indexOf("export function HarmonicDiagramDialog", start);
  assert.ok(start >= 0 && end > start);
  const dialog = source.slice(start, end);
  const copy = dialog.slice(dialog.indexOf("async function copy()"), dialog.indexOf("async function saveText()"));
  const save = dialog.slice(dialog.indexOf("async function saveText()"), dialog.indexOf("  return (", dialog.indexOf("async function saveText()")));
  for (const action of [copy, save]) {
    assert.match(action, /await appendOnce\.current\(async \(\) => \{/);
    assert.match(action, /finally\s*\{\s*setOutputting\(null\)/);
  }
  assert.match(dialog, /const busy = appending \|\| choosing \|\| outputting !== null/);
  assert.match(dialog, /setOutputting\("copy"\)/);
  assert.match(dialog, /setOutputting\("save"\)/);
  assert.match(dialog, /<Modal title="Quick Hz ツール" onClose=\{onClose\} wide locked=\{busy\}>/);
});
