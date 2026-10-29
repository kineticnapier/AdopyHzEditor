import assert from "node:assert/strict";
import test from "node:test";
import { quickHzActionPolicy } from "../src/dialogs/quickHzActionPolicy.ts";

test("pending chart append locks every setting and action", () => {
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
