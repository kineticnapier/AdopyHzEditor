import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { exportFailureMessage } from "../src/dialogs/exportResult.ts";

test("failed ADOFAI export responses show their reason", () => {
  assert.equal(exportFailureMessage({ ok: false, status: "Audio source not found: missing.ogg" }), "Audio source not found: missing.ogg");
  assert.equal(exportFailureMessage({ ok: false, status: "Audio copy cancelled: file exists" }), "Audio copy cancelled: file exists");
});

test("successful export and native Save cancellation do not show errors", () => {
  assert.equal(exportFailureMessage({ ok: true, status: "Exported level.adofai" }), null);
  assert.equal(exportFailureMessage({ ok: false, status: "Cancelled" }), null);
  assert.equal(exportFailureMessage({ ok: false, status: "キャンセルしました" }), null);
});

test("failed export with empty status has a readable fallback", () => {
  assert.equal(exportFailureMessage({ ok: false, status: "  " }), "ADOFAIの書き出しに失敗しました");
});

test("ADOFAI dialog displays resolved export failures in its alert", () => {
  const source = readFileSync(new URL("../src/dialogs/AdoFAIExportDialogJa.tsx", import.meta.url), "utf8");
  const exportAction = source.slice(source.indexOf("async function exportLevel()"), source.indexOf("async function tilePreview()"));
  assert.match(exportAction, /const failure = exportFailureMessage\(r\)/);
  assert.match(exportAction, /if \(failure\) setError\(\{ message: failure, context \}\)/);
  assert.match(source, /\{currentError && <div className="dialog-error" role="alert">\{currentError\}<\/div>\}/);
});
