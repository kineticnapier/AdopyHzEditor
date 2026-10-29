import assert from "node:assert/strict";
import test from "node:test";
import { runReleasePageAction } from "../src/dialogs/releasePageAction.ts";
import { dismissUnlessBusy } from "../src/dialogs/dialogClosePolicy.ts";
import { createExclusiveAsyncAction } from "../src/dialogs/exclusiveAsyncAction.ts";

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

test("pending release-page launch blocks dismissal and unlocks after failure", async () => {
  let resolve!: (result: { ok: boolean; url: string }) => void;
  const response = new Promise<{ ok: boolean; url: string }>(r => { resolve = r; });
  const once = createExclusiveAsyncAction();
  let opening = false, closes = 0, errors = 0;
  const launch = () => once(async () => {
    opening = true;
    try {
      await runReleasePageAction(
        () => response,
        () => { closes++; },
        () => { errors++; },
      );
    } finally {
      opening = false;
    }
  });
  const pending = launch();
  assert.equal(dismissUnlessBusy(opening, () => { closes++; }), false);
  assert.equal(await launch(), undefined);
  assert.equal(closes, 0);
  resolve({ ok: false, url: "https://example.com/releases" });
  await pending;
  assert.equal(errors, 1);
  assert.equal(closes, 0);
  assert.equal(opening, false);
  assert.equal(dismissUnlessBusy(opening, () => { closes++; }), true);
  assert.equal(closes, 1);
});

test("successful release-page launch closes once without early dismissal", async () => {
  let resolve!: (result: { ok: boolean; url: string }) => void;
  const response = new Promise<{ ok: boolean; url: string }>(r => { resolve = r; });
  let opening = false, closes = 0;
  const launch = createExclusiveAsyncAction();
  const pending = launch(async () => {
    opening = true;
    try {
      await runReleasePageAction(() => response, () => { closes++; }, () => {});
    } finally {
      opening = false;
    }
  });
  assert.equal(dismissUnlessBusy(opening, () => { closes++; }), false);
  resolve({ ok: true, url: "https://example.com/releases" });
  await pending;
  assert.equal(closes, 1);
  assert.equal(opening, false);
});
