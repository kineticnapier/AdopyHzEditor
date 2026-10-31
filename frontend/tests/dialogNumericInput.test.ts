import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { commitNumericEdit } from "../src/settings/numericInputModel.ts";

const dialogFiles = [
  "../src/dialogs/ToolDialogs.tsx",
  "../src/dialogs/AdoFAIExportDialogJa.tsx",
];

for (const file of dialogFiles) {
  test(`${file} preserves draft text until blur or Enter`, () => {
    const source = readFileSync(new URL(file, import.meta.url), "utf8").replace(/\r\n/g, "\n");
    const start = source.indexOf("function Num({");
    assert.ok(start >= 0, "numeric field component exists");
    const end = source.indexOf("\n}\n", start);
    assert.ok(end > start, "numeric field component closes");
    const component = source.slice(start, end + 2);

    assert.match(component, /value=\{text\}/);
    assert.match(component, /onChange=\{\(event\) => setText\(event\.target\.value\)\}/);
    assert.match(component, /onBlur=\{commit\}/);
    assert.match(component, /commitNumericEdit\(text, fallback, min, max, cancelledRef\.current\)/);
    assert.match(component, /cancelledRef\.current = true/);
    assert.match(component, /event\.stopPropagation\(\)/);
    assert.doesNotMatch(component, /Number\(event\.target\.value\)/);
  });
}

test("numeric dialog inputs leave composition keys to the IME", () => {
  for (const file of dialogFiles) {
    const source = readFileSync(new URL(file, import.meta.url), "utf8").replace(/\r\n/g, "\n");
    assert.match(source, /import \{ isDialogCompositionKey \} from "\.\/dialogFocus";/);
    const start = source.indexOf("function Num({");
    const end = source.indexOf("\n}\n", start);
    assert.ok(start >= 0 && end > start, "numeric component exists");
    const component = source.slice(start, end + 2);
    // The local handler runs before the window-level dialog focus handler.
    assert.match(component, /onKeyDown=\{\(event\) => \{[\s\S]*?if \(isDialogCompositionKey\(event\.nativeEvent\)\) return;[\s\S]*?if \(event\.key === "Enter"\)/);
    assert.match(component, /else if \(event\.key === "Escape"\)/);
  }
});

test("tool dialogs commit signed decimals and restore cancelled/blank edits", () => {
  assert.equal(commitNumericEdit("-123.5", 0, -3600000, 3600000, false), -123.5);
  assert.equal(commitNumericEdit("0.125", 16, 0.001, 100000, false), 0.125);
  assert.equal(commitNumericEdit("", 16, 0.001, 100000, false), 16);
  assert.equal(commitNumericEdit("-", 16, -100000, 100000, false), 16);
  assert.equal(commitNumericEdit("1234", 16, 0, 127, false), 127);
  assert.equal(commitNumericEdit("-42", 16, -100000, 100000, true), 16);
});

test("Quick Hz range has a named group and separately named controls", () => {
  const source = readFileSync(new URL("../src/dialogs/ToolDialogs.tsx", import.meta.url), "utf8");
  const start = source.indexOf('<Field label="生成範囲" group>');
  assert.ok(start >= 0);
  const end = source.indexOf("</Field>", start);
  assert.ok(end > start);
  const group = source.slice(start, end);
  assert.match(source, /<div className="dialog-field" role="group" aria-label=\{label\}>/);
  assert.match(group, /<label>[\s\S]*?終了床で指定[\s\S]*?<\/label>/);
  assert.match(group, /label="終了床"/);
  assert.match(group, /label="生成数"/);
  const numeric = source.slice(source.indexOf("function Num({"), source.indexOf("function LoadFailure("));
  assert.match(numeric, /type="number"\s+aria-label=\{label\}/);
});

test("Quick Hz output preview is named and tool errors are announced", () => {
  const source = readFileSync(new URL("../src/dialogs/ToolDialogs.tsx", import.meta.url), "utf8");
  assert.match(source, /<textarea aria-label="Quick Hz出力プレビュー"[^>]*readOnly/);
  const inlineErrors = source.match(/<div className="dialog-error inline" role="alert">\{error\}<\/div>/g);
  assert.equal(inlineErrors?.length, 2, "both tool error panels announce failures");
});

test("tool dialog load failures are announced as alerts", () => {
  const source = readFileSync(new URL("../src/dialogs/ToolDialogs.tsx", import.meta.url), "utf8");
  const start = source.indexOf("function LoadFailure(");
  const end = source.indexOf("\nexport function BlankWorkspaceDialog(", start);
  assert.ok(start >= 0 && end > start, "shared load failure component exists");
  const component = source.slice(start, end);
  assert.match(component, /<div className="dialog-error" role="alert">読込に失敗しました: \{error\}<\/div>/);
  assert.ok((source.match(/<LoadFailure\b/g) ?? []).length >= 2, "the shared error component is reused");
});

test("ADOFAI export defaults failure is announced and busy dialog state is exposed", () => {
  const source = readFileSync(new URL("../src/dialogs/AdoFAIExportDialogJa.tsx", import.meta.url), "utf8").replace(/\r\n/g, "\n");
  assert.match(source, /<div className="dialog-error" role="alert">\s*設定の読込に失敗しました: \{error\}/);
  const modalStart = source.indexOf("function Modal({");
  assert.ok(modalStart >= 0, "ADOFAI export modal exists");
  const modal = source.slice(modalStart);
  assert.match(modal, /aria-modal="true"[\s\S]*?aria-labelledby=\{titleId\}[\s\S]*?aria-busy=\{locked\}/);
  assert.match(source, /<Modal[\s\S]*?locked=\{working\}/);
});
