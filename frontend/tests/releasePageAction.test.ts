import assert from "node:assert/strict";
import test from "node:test";
import { runReleasePageAction } from "../src/dialogs/releasePageAction.ts";

test("release page success reports completion", async () => {
  const calls: string[] = [];
  await runReleasePageAction(
    async () => ({ ok: true, url: "https://example.com/releases" }),
    () => calls.push("opened"),
    message => calls.push(message),
  );
  assert.deepEqual(calls, ["opened"]);
});

test("browser launch returning false keeps the dialog open and displays the URL", async () => {
  const calls: string[] = [];
  await runReleasePageAction(
    async () => ({ ok: false, url: "https://example.com/releases" }),
    () => calls.push("opened"),
    message => calls.push(message),
  );
  assert.deepEqual(calls, ["リリースページを開けませんでした。URL: https://example.com/releases"]);
});

test("backend rejection reports the error instead of leaving an unhandled rejection", async () => {
  const calls: string[] = [];
  await runReleasePageAction(
    async () => { throw new Error("browser unavailable"); },
    () => calls.push("opened"),
    message => calls.push(message),
  );
  assert.deepEqual(calls, ["リリースページを開けませんでした: Error: browser unavailable"]);
});

test("the action can be retried after a failed launch", async () => {
  let attempts = 0;
  let opened = 0;
  const errors: string[] = [];
  const open = async () => ({ ok: ++attempts === 2, url: "https://example.com/releases" });
  await runReleasePageAction(open, () => opened++, message => errors.push(message));
  await runReleasePageAction(open, () => opened++, message => errors.push(message));
  assert.equal(attempts, 2);
  assert.equal(opened, 1);
  assert.equal(errors.length, 1);
});
