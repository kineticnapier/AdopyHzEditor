import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { exportFailureMessage, exportStatusMessage } from "../src/dialogs/exportResult.ts";

test("cancelling the native save dialog leaves the editor status unchanged", () => {
  for (const status of ["Cancelled", "cancelled", "キャンセルしました"]) {
    const result = { ok: false, status };
    assert.equal(exportFailureMessage(result), null);
    assert.equal(exportStatusMessage(result), null);
  }
});

test("successful exports and actual failures still report a useful status", () => {
  assert.equal(exportStatusMessage({ ok: true, status: "Exported level.adofai" }), "Exported level.adofai");
  assert.equal(exportStatusMessage({ ok: false, status: "Audio source not found" }), "Audio source not found");
  assert.equal(exportStatusMessage({ ok: false, status: "" }), "ADOFAIの書き出しに失敗しました");
});

test("ADOFAI export action only publishes non-cancelled status", () => {
  const source = readFileSync(new URL("../src/dialogs/AdoFAIExportDialogJa.tsx", import.meta.url), "utf8");
  const action = source.slice(source.indexOf("async function exportLevel()"), source.indexOf("async function tilePreview()"));
  assert.match(action, /const status = exportStatusMessage\(r\)/);
  assert.match(action, /if \(status !== null\) onStatus\(status\)/);
  assert.doesNotMatch(action, /onStatus\(r\.status\)/);
});
