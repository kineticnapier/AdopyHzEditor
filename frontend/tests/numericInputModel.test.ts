import assert from "node:assert/strict";
import test from "node:test";
import { readFileSync } from "node:fs";
import { isDialogCompositionKey } from "../src/dialogs/dialogFocus.ts";
import { commitNumericText, commitNumericEdit } from "../src/settings/numericInputModel.ts";

test("transient numeric strings keep the prior committed value", () => {
  assert.equal(commitNumericText("", 12.5, 0, 127), 12.5);
  assert.equal(commitNumericText("-", 12.5, 0, 127), 12.5);
  assert.equal(commitNumericText("1e", 12.5, 0, 127), 12.5);
});

test("committed numeric values retain fractions and clamp to bounds", () => {
  assert.equal(commitNumericText("60.25", 0, 0, 127), 60.25);
  assert.equal(commitNumericText("200", 0, 0, 127), 127);
});

test("Escape cancels the edit even when blur sees stale text", () => {
  assert.equal(commitNumericEdit("2.000", 1, 0, 36000, true), 1);
  assert.equal(commitNumericEdit("-4", 12, -600000, 600000, true), 12);
});

test("Enter and blur still commit valid values", () => {
  assert.equal(commitNumericEdit("2.000", 1, 0, 36000, false), 2);
  assert.equal(commitNumericEdit("-4", 12, -600000, 600000, false), -4);
  assert.equal(commitNumericEdit("200", 10, 0, 127, false), 127);
});


test("numeric inputs defer Enter and Escape to the IME", () => {
  assert.equal(isDialogCompositionKey({ isComposing: true, keyCode: 13 }), true);
  assert.equal(isDialogCompositionKey({ isComposing: false, keyCode: 229 }), true);
  assert.equal(isDialogCompositionKey({ isComposing: false, keyCode: 13 }), false);
});

test("settings numeric input ignores IME keys and disabled blur", () => {
  const source = readFileSync(new URL("../src/settings/SettingsPanel.tsx", import.meta.url), "utf8")
    .replace(/\r\n/g, "\n");
  const start = source.indexOf("function NumberInput(");
  const end = source.indexOf("\nfunction Select(", start);
  assert.ok(start >= 0 && end > start, "settings numeric input is present");
  const input = source.slice(start, end);
  const disabled = input.indexOf("if (disabled) {");
  const commit = input.indexOf("const next = commitNumericEdit(");
  assert.ok(disabled >= 0 && commit > disabled, "disabled blur must not commit an old value");
  const composition = input.indexOf("if (isDialogCompositionKey(e.nativeEvent)) return;");
  const enter = input.indexOf('if (e.key === "Enter")');
  const escape = input.indexOf('else if (e.key === "Escape")');
  assert.ok(composition >= 0 && enter > composition && escape > enter,
    "IME composition must be checked before Enter/Escape handling");
  assert.match(input.slice(escape), /e\.stopPropagation\(\)/,
    "cancelled numeric Escape must not bubble to editor shortcuts");
});

test("fractional playback and timing settings are valid in the HTML inputs", () => {
  const source = readFileSync(new URL("../src/settings/SettingsPanel.tsx", import.meta.url), "utf8")
    .replace(/\r\n/g, "\n");
  for (const [label, example, min, max] of [
    ["再生速度", "1.03", 0.1, 4],
    ["BPM", "123.45", 1, 10000],
    ["オフセット", "0.5", -600000, 600000],
    ["目標角度", "123.4567", 0.001, 359.999],
  ] as const) {
    const start = source.indexOf(`<Row label="${label}">`);
    assert.ok(start >= 0, `${label} row exists`);
    const end = source.indexOf("</Row>", start);
    assert.ok(end > start, `${label} row is complete`);
    const row = source.slice(start, end);
    assert.match(row, /<NumberInput[\s\S]*?step="any"/, `${label} must accept API-valid fractions`);
    assert.equal(commitNumericText(example, 0, min, max), Number(example));
  }
});

test("fractional inspector note and bulk edits are not rejected by HTML step constraints", () => {
  const source = readFileSync(new URL("../src/settings/SettingsPanel.tsx", import.meta.url), "utf8")
    .replace(/\r\n/g, "\n");
  const bulkStart = source.indexOf("function BulkEditor(");
  const bulkEnd = source.indexOf("function Fold(", bulkStart);
  assert.ok(bulkStart >= 0 && bulkEnd > bulkStart, "bulk editor boundaries exist");

  for (const [section, cases] of [
    [source.slice(0, bulkStart), [
      ["開始", "0.0005", 0, 36000],
      ["終了", "1.00025", 0, 36000],
      ["長さ", "0.0015", 0.001, 36000],
      ["MIDI", "60.125", 0, 127],
    ]],
    [source.slice(bulkStart, bulkEnd), [
      ["時間移動", "0.0005", -36000, 36000],
      ["音高移動", "0.125", -127, 127],
      ["長さ", "0.0015", 0.001, 36000],
    ]],
  ] as const) {
    for (const [label, example, min, max] of cases) {
      const start = section.indexOf(`<Row label="${label}">`);
      assert.ok(start >= 0, `${label} row exists`);
      const end = section.indexOf("</Row>", start);
      assert.ok(end > start, `${label} row is complete`);
      const row = section.slice(start, end);
      assert.match(row, /<NumberInput[\s\S]*?step="any"/, `${label} accepts API-valid fractions`);
      assert.equal(commitNumericText(example, 0, min, max), Number(example));
    }
  }
});

test("whole-step settings inputs normalize fractions before sending to the API", () => {
  assert.equal(commitNumericEdit("1.4", 1, 1, 64, false, true), 1);
  assert.equal(commitNumericEdit("1.6", 1, 1, 64, false, true), 2);
  assert.equal(commitNumericEdit("-1.6", 0, -12, 12, false, true), -2);
  assert.equal(commitNumericEdit("1.4", 1, 1, 64, false, false), 1.4);
  assert.equal(commitNumericEdit("", 1, 1, 64, false, true), 1);
  assert.equal(commitNumericEdit("2.5", 1, 1, 64, true, true), 1);
});

test("settings panel passes whole-step information to numeric commit", () => {
  const source = readFileSync(new URL("../src/settings/SettingsPanel.tsx", import.meta.url), "utf8")
    .replace(/\r\n/g, "\n");
  const start = source.indexOf("function NumberInput(");
  const end = source.indexOf("\nfunction Select(", start);
  assert.ok(start >= 0 && end > start);
  const component = source.slice(start, end);
  assert.match(component, /commitNumericEdit\([\s\S]*?cancelledRef\.current,\s*step === 1,/);
});
