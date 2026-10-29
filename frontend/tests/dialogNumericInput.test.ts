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
    const source = readFileSync(new URL(file, import.meta.url), "utf8");
    const start = source.indexOf("function Num({");
    assert.ok(start >= 0, "numeric field component exists");
    const end = source.indexOf("\n}", start);
    assert.ok(end > start, "numeric field component closes");
    const component = source.slice(start, end + 2);

    assert.match(component, /value=\{text\}/);
    assert.match(component, /onChange=\{\(event\) => setText\(event\.target\.value\)\}/);
    assert.match(component, /onBlur=\{commit\}/);
    assert.match(component, /commitNumericEdit\(text, fallback, min, max, cancelledRef\.current\)/);
    assert.match(component, /cancelledRef\.current = true/);
    assert.doesNotMatch(component, /Number\(event\.target\.value\)/);
  });
}

test("tool dialogs commit signed decimals and restore cancelled/blank edits", () => {
  assert.equal(commitNumericEdit("-123.5", 0, -3600000, 3600000, false), -123.5);
  assert.equal(commitNumericEdit("0.125", 16, 0.001, 100000, false), 0.125);
  assert.equal(commitNumericEdit("", 16, 0.001, 100000, false), 16);
  assert.equal(commitNumericEdit("-", 16, -100000, 100000, false), 16);
  assert.equal(commitNumericEdit("1234", 16, 0, 127, false), 127);
  assert.equal(commitNumericEdit("-42", 16, -100000, 100000, true), 16);
});
