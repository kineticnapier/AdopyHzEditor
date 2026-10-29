import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const source = readFileSync(
  new URL("../src/dialogs/ToolDialogs.tsx", import.meta.url),
  "utf8",
);
const styles = readFileSync(
  new URL("../src/tools.css", import.meta.url),
  "utf8",
);
const harmonic = source.slice(
  source.indexOf("export function HarmonicDiagramDialog("),
  source.indexOf("export function LanguageDialog("),
);

test("harmonic insertion disables every editable setting without hiding the preview", () => {
  const formStart = harmonic.indexOf('<fieldset className="tool-form harmonic-form" disabled={inserting}>');
  const formEnd = harmonic.indexOf("</fieldset>", formStart);
  assert.ok(formStart >= 0 && formEnd > formStart);
  const form = harmonic.slice(formStart, formEnd);
  for (const label of [
    "基準周波数", "基準倍率", "1次元オフセット", "倍音列",
    "時間単位", "BPM", "開始", "長さ", "EDO", "番号オフセット",
  ]) assert.ok(form.includes(`<Field label="${label}">`), label);
  assert.ok(harmonic.indexOf('<section className="harmonic-preview">') > formEnd);
  assert.match(harmonic, /locked={inserting}/);
  assert.match(harmonic, /disabled={inserting \|\| !previewCurrent}/);
});

test("harmonic changes are rejected synchronously while the insertion is pending", () => {
  assert.match(harmonic, /const insertingRef = useRef\(false\);/);
  assert.match(harmonic, /function updateOpts\(next: HarmonicDiagramOptions\) \{[\s\S]*?if \(!insertingRef\.current\) setOpts\(next\);/);
  const insert = harmonic.slice(harmonic.indexOf("async function insert()"), harmonic.indexOf("if (!opts && error)"));
  assert.match(insert, /await insertOnce\.current\(async \(\) => \{\s*insertingRef\.current = true;\s*setInserting\(true\);/);
  assert.match(insert, /finally \{\s*insertingRef\.current = false;\s*setInserting\(false\);/);
  const form = harmonic.slice(harmonic.indexOf('<fieldset className="tool-form harmonic-form"'), harmonic.indexOf("</fieldset>"));
  assert.ok(!form.includes("setOpts("), "form must not bypass the busy guard");
  assert.ok((form.match(/updateOpts\(/g) ?? []).length >= 9);
});

test("a disabled numeric input cannot commit its pending blur edit", () => {
  const num = source.slice(source.indexOf("function Num({"), source.indexOf("function LoadFailure("));
  const commit = num.slice(num.indexOf("function commit()"), num.indexOf("return (", num.indexOf("function commit()")));
  assert.match(commit, /if \(disabled\) \{/);
  assert.ok(commit.indexOf("if (disabled)") < commit.indexOf("onChange(next)"));
  assert.match(commit, /setText\(String\(fallback\)\);/);
});

test("disabled harmonic fieldset keeps the previous grid dimensions", () => {
  assert.match(styles, /\.harmonic-form\{[^}]*margin:0;[^}]*padding:0;[^}]*border:0;[^}]*min-inline-size:0/);
});
