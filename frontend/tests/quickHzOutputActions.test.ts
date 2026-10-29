import assert from "node:assert/strict";
import test from "node:test";
import { runQuickHzOutputAction } from "../src/dialogs/quickHzOutputActions.ts";

test("Quick Hz copy success reports completion after clipboard resolves", async () => {
  const calls: string[] = [];
  await runQuickHzOutputAction(
    "コピー",
    async () => { calls.push("write"); },
    () => calls.push("copied"),
    message => calls.push(`error:${message}`),
  );
  assert.deepEqual(calls, ["write", "copied"]);
});

test("Quick Hz copy rejection is displayed and never reports success", async () => {
  const calls: string[] = [];
  await runQuickHzOutputAction(
    "コピー",
    () => Promise.reject(new Error("permission denied")),
    () => calls.push("copied"),
    message => calls.push(message),
  );
  assert.deepEqual(calls, ["コピーに失敗しました: Error: permission denied"]);
});

test("Quick Hz save rejection is displayed without an unhandled rejection", async () => {
  const calls: string[] = [];
  await runQuickHzOutputAction(
    "テキスト保存",
    async () => { throw new Error("disk full"); },
    result => calls.push(String(result)),
    message => calls.push(message),
  );
  assert.deepEqual(calls, ["テキスト保存に失敗しました: Error: disk full"]);
});

test("Quick Hz save success retains backend status", async () => {
  const calls: string[] = [];
  await runQuickHzOutputAction(
    "テキスト保存",
    async () => ({ ok: true, status: "保存しました" }),
    result => calls.push(result.status),
    message => calls.push(message),
  );
  assert.deepEqual(calls, ["保存しました"]);
});
