import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { LatestRequestGate } from "../src/api/requestCoordinator.ts";
import { createExclusiveAsyncAction } from "../src/dialogs/exclusiveAsyncAction.ts";

const dialogSource = readFileSync(
  new URL("../src/dialogs/AdoFAIExportDialogJa.tsx", import.meta.url),
  "utf8",
);

test("ADOFAI export settings are disabled during an operation", () => {
  const start = dialogSource.indexOf("<fieldset\n          disabled={working}");
  const end = dialogSource.indexOf("</fieldset>", start);
  assert.ok(start > 0 && end > start, "settings must be wrapped in a disabled fieldset");
  const settings = dialogSource.slice(start, end);
  assert.match(settings, /<Field label="方式">/);
  assert.match(settings, /<details className="advanced-fold">/);
  assert.match(settings, /<Field label="最大床数">/);
  assert.match(dialogSource, /locked={working}/);
  const patch = dialogSource.slice(
    dialogSource.indexOf("function patch<"),
    dialogSource.indexOf("async function run<"),
  );
  assert.match(patch, /if \(workingRef\.current\) return;/);
  assert.match(dialogSource, /return actionOnce\.current\(async \(\) => \{/);
});

test("a rejected duplicate preview does not invalidate the accepted preview", async () => {
  const exclusive = createExclusiveAsyncAction();
  const gate = new LatestRequestGate();
  let release!: () => void;
  let calls = 0;
  const start = () => exclusive(async () => {
    const request = gate.issue();
    calls += 1;
    await new Promise<void>(resolve => { release = resolve; });
    return { request, preview: "first" };
  });
  const first = start();
  assert.equal(await start(), undefined);
  assert.equal(calls, 1);
  assert.equal(gate.isCurrent(1), true);
  release();
  const result = await first;
  assert.equal(result?.preview, "first");
  assert.equal(gate.isCurrent(result!.request), true);
});

test("ADOFAI preview generation is issued inside the exclusive action", () => {
  for (const [name, next, method] of [
    ["tilePreview", "debugPreview", "preview_adofai_tiles"],
    ["debugPreview", "chooseSongSource", "preview_adofai_debug"],
  ]) {
    const section = dialogSource.slice(
      dialogSource.indexOf(`async function ${name}()`),
      dialogSource.indexOf(`async function ${next}()`),
    );
    assert.match(section, /run\(async \(\) => \{\s*const request = previewRequests\.current\.issue\(\);/);
    assert.ok(section.includes(`await api.${method}(`));
    assert.match(section, /previewRequests\.current\.isCurrent\(r\.request\)/);
  }
});

test("a failed export action permits a subsequent attempt", async () => {
  const exclusive = createExclusiveAsyncAction();
  let calls = 0;
  await assert.rejects(exclusive(async () => {
    calls += 1;
    throw new Error("export failed");
  }), /export failed/);
  assert.equal(await exclusive(async () => {
    calls += 1;
    return "retry ok";
  }), "retry ok");
  assert.equal(calls, 2);
});
