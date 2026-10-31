import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const source = readFileSync(
  new URL("../src/dialogs/AdoFAIExportDialogJa.tsx", import.meta.url),
  "utf8",
);

test("selection refresh disables export until new defaults arrive", () => {
  const effectStart = source.indexOf("previewRequests.current.invalidate();");
  const loadStart = source.indexOf(".get_adofai_export_defaults(selected)", effectStart);
  assert.ok(effectStart >= 0 && loadStart > effectStart);
  const effect = source.slice(effectStart, loadStart);
  assert.match(effect, /setOptions\(null\)/);
  assert.ok(effect.indexOf("setOptions(null)") < loadStart - effectStart);
  assert.match(source, /if \(!options\)\s*return\s*\(/);
  assert.match(source, /if \(alive\) setOptions\(/);
});

test("export and preview failures are announced to assistive technology", () => {
  assert.match(source, /\{error && <div className="dialog-error" role="alert">\{error\}<\/div>\}/);
  assert.match(source, /setError\(String\(e\)\)/);
});

test("selection refresh cannot unlock a still-running export", () => {
  const loadingStart = source.indexOf("if (!options)");
  const loadedStart = source.indexOf("const isHarmony", loadingStart);
  assert.ok(loadingStart >= 0 && loadedStart > loadingStart);
  const loading = source.slice(loadingStart, loadedStart);
  // The loading branch must preserve the same lock as the normal export form.
  assert.match(loading, /<Modal title="ADOFAI出力" onClose=\{onClose\} locked=\{working\}>/);
  assert.match(loading, /className="primary"\s+disabled=\{working\}\s+onClick=\{\(\) => setLoadAttempt/);
  assert.match(loading, /className="dialog-loading" role="status"/);
  assert.match(loading, /working \? "出力処理中…"/);
});
