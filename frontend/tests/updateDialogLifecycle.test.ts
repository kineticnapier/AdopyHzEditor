import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { blankWorkspaceDefaultsContextIsCurrent } from "../src/dialogs/previewFreshness.ts";
import { runReleasePageAction } from "../src/dialogs/releasePageAction.ts";

const source = readFileSync(new URL("../src/dialogs/ToolDialogs.tsx", import.meta.url), "utf8");
const update = source.slice(source.indexOf("export function UpdateDialog("));

test("update information and errors are scoped to the API and retry", () => {
  const api = {};
  const old = { api, attempt: 0 };
  assert.equal(blankWorkspaceDefaultsContextIsCurrent(old, old), true);
  assert.equal(blankWorkspaceDefaultsContextIsCurrent(old, { api: {}, attempt: 0 }), false);
  assert.equal(blankWorkspaceDefaultsContextIsCurrent(old, { api, attempt: 1 }), false);
  assert.match(update, /blankWorkspaceDefaultsContextIsCurrent\(info, context\)/);
  assert.match(update, /blankWorkspaceDefaultsContextIsCurrent\(error, context\)/);
  assert.match(update, /blankWorkspaceDefaultsContextIsCurrent\(openError, context\)/);
  assert.match(update, /setInfo\(null\)/);
  assert.match(update, /setError\(null\)/);
  assert.match(update, /setInfo\(\{ api, attempt, value \}\)/);
  assert.match(update, /setError\(\{ api, attempt, message: String\(reason\) \}\)/);
  assert.match(update, /\[api, attempt\]/);
  assert.match(update, /currentError \?/);
  assert.match(update, /currentInfo \?/);
  assert.match(update, /role="status">確認中/);
});

test("stale release launch completion cannot close the current update dialog", async () => {
  const original = { api: {}, attempt: 0 };
  let current = original;
  let finish!: (value: { ok: boolean; url: string }) => void;
  const pending = new Promise<{ ok: boolean; url: string }>(resolve => { finish = resolve; });
  const events: string[] = [];
  const task = runReleasePageAction(
    () => pending,
    () => { if (blankWorkspaceDefaultsContextIsCurrent(original, current)) events.push("close"); },
    message => { if (blankWorkspaceDefaultsContextIsCurrent(original, current)) events.push(message); },
  );
  current = { api: {}, attempt: 0 };
  finish({ ok: true, url: "https://example.com/releases" });
  await task;
  assert.deepEqual(events, []);
  assert.match(update, /latestContext\.current = context/);
  assert.match(update, /if \(!blankWorkspaceDefaultsContextIsCurrent\(context, latestContext\.current\)\) return/);
  assert.match(update, /if \(blankWorkspaceDefaultsContextIsCurrent\(context, latestContext\.current\)\)/);
});

test("current release launch still reports success or failure", async () => {
  const events: string[] = [];
  await runReleasePageAction(
    async () => ({ ok: true, url: "https://example.com/releases" }),
    () => events.push("close"),
    message => events.push(message),
  );
  await runReleasePageAction(
    async () => ({ ok: false, url: "https://example.com/releases" }),
    () => events.push("close"),
    message => events.push(message),
  );
  assert.equal(events[0], "close");
  assert.match(events[1], /リリースページを開けませんでした/);
  assert.match(update, /locked=\{opening\}/);
  assert.match(update, /disabled=\{opening\}/);
});
