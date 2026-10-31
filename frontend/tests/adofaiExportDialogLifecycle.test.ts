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
