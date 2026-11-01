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

test("tool dialog group fields and harmonic errors are accessible", () => {
  const source = readFileSync(new URL("../src/dialogs/ToolDialogs.tsx", import.meta.url), "utf8");
  assert.match(source, /<div className="dialog-field" role="group" aria-label=\{label\}>/);
  const numeric = source.slice(source.indexOf("function Num({"), source.indexOf("function LoadFailure("));
  assert.match(numeric, /type="number"\s+aria-label=\{label\}/);
  assert.match(source, /<div className="dialog-error inline" role="alert">\{currentError\}<\/div>/);
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
  assert.match(source, /<div className="dialog-error" role="alert">\s*設定の読込に失敗しました: \{currentError\}/);
  const modalStart = source.indexOf("function Modal({");
  assert.ok(modalStart >= 0, "ADOFAI export modal exists");
  const modal = source.slice(modalStart);
  assert.match(modal, /aria-modal="true"[\s\S]*?aria-labelledby=\{titleId\}[\s\S]*?aria-busy=\{locked\}/);
  assert.match(source, /<Modal[\s\S]*?locked=\{working\}/);
});

test("harmonic frequency and duration accept decimals without native step mismatch", () => {
  const source = readFileSync(new URL("../src/dialogs/ToolDialogs.tsx", import.meta.url), "utf8").replace(/\r\n/g, "\n");
  const harmonic = source.slice(
    source.indexOf("export function HarmonicDiagramDialog("),
    source.indexOf("export function LanguageDialog("),
  );
  assert.ok(harmonic.length > 0, "harmonic dialog exists");
  // min=0.001 with step=1 or 0.25 rejects ordinary values such as
  // 440 Hz and 1 second under the browser's native step-mismatch rules.
  for (const field of ["rootHz", "duration"]) {
    const control = harmonic.match(new RegExp(`<Num\\s+value=\\{opts\\.${field}\\}[\\s\\S]*?\\/>`))?.[0];
    assert.ok(control, `missing ${field} input`);
    assert.match(control, /min=\{0\.001\}/);
    assert.match(control, /step="any"/);
  }
});

test("tool dialogs accept fractional values returned by the backend", () => {
  const source = readFileSync(new URL("../src/dialogs/ToolDialogs.tsx", import.meta.url), "utf8").replace(/\r\n/g, "\n");
  const blank = source.slice(
    source.indexOf("export function BlankWorkspaceDialog("),
    source.indexOf("export function HarmonicDiagramDialog("),
  );
  const harmonic = source.slice(
    source.indexOf("export function HarmonicDiagramDialog("),
    source.indexOf("export function LanguageDialog("),
  );
  // Python returns the current duration, playhead position and BPM as floats.
  // HTML's default step=1 or step=0.25 rejects valid values from those APIs.
  for (const [section, field] of [
    [blank, "value.duration"],
    [harmonic, "opts.bpm"],
    [harmonic, "opts.start"],
  ] as const) {
    const start = section.indexOf(`value={${field}}`);
    assert.ok(start >= 0, `missing ${field} input`);
    const end = section.indexOf("/>", start);
    assert.ok(end > start, `missing end of ${field} input`);
    assert.match(section.slice(start, end), /step="any"/, `${field} must accept fractional values`);
  }
});

test("ADOFAI export accepts its backend default fixed X and custom angle", () => {
  const source = readFileSync(new URL("../src/dialogs/AdoFAIExportDialogJa.tsx", import.meta.url), "utf8").replace(/\r\n/g, "\n");
  // Python defaults: fixedX=8.0, finalCustomAngle=180.0. Their previous
  // min+step combinations (0.000001+0.1n and 0.001+1n) reject both.
  for (const [field, min] of [["fixedX", "0.000001"], ["finalCustomAngle", "0.001"]] as const) {
    const start = source.indexOf(`value={options.${field}}`);
    assert.ok(start >= 0, `missing ${field} input`);
    const end = source.indexOf("/>", start);
    assert.ok(end > start, `missing end of ${field} input`);
    const control = source.slice(start, end);
    assert.ok(control.includes(`min={${min}}`), `unexpected minimum for ${field}`);
    assert.match(control, /step="any"/, `${field} must not reject its backend default`);
  }
});


test("ADOFAI export accepts fractional values for every Python float option", () => {
  const source = readFileSync(new URL("../src/dialogs/AdoFAIExportDialogJa.tsx", import.meta.url), "utf8").replace(/\r\n/g, "\n");
  const backend = readFileSync(new URL("../../web/adofai.py", import.meta.url), "utf8");
  const continuous = [
    "baseBpm",
    "angleOnlyBpm",
    "harmonyCustomSemitone",
    "targetBpm",
    "visualPathAngle",
    "visualPositionX",
    "visualPositionY",
    "finalCardinalStep",
    "harmonyVisualStep",
    "harmonyPolyCycleAngle",
    "songOffsetMs",
  ] as const;
  for (const field of continuous) {
    // These inputs are parsed with _as_float by the backend. The native HTML
    // step constraint must not reject values that the backend accepts.
    assert.ok(backend.includes(`_as_float(raw.get("${field}")`), `backend must parse ${field} as float`);
    const start = source.indexOf(`value={options.${field}}`);
    assert.ok(start >= 0, `missing ${field} control`);
    const end = source.indexOf("/>", start);
    assert.ok(end > start && end - start < 500, `missing end of ${field} control`);
    assert.match(source.slice(start, end), /step="any"/, `${field} must allow fractional values`);
  }
});

test("ADOFAI export tile limits accept every backend-supported integer", () => {
  const source = readFileSync(new URL("../src/dialogs/AdoFAIExportDialogJa.tsx", import.meta.url), "utf8").replace(/\r\n/g, "\n");
  const backend = readFileSync(new URL("../../web/adofai.py", import.meta.url), "utf8");
  // The backend accepts arbitrary integer counts, not only multiples of
  // 10000 (maxTiles) or 500 (maxTilesPerNote). HTML must agree.
  for (const field of ["maxTiles", "maxTilesPerNote"] as const) {
    assert.ok(backend.includes(`_as_int(raw.get("${field}")`), `backend must parse ${field} as int`);
    const start = source.indexOf(`value={options.${field}}`);
    assert.ok(start >= 0, `missing ${field} input`);
    const end = source.indexOf("/>", start);
    assert.ok(end > start && end - start < 500, `missing end of ${field} input`);
    const control = source.slice(start, end);
    assert.match(control, /min=\{0\}/);
    assert.match(control, /step=\{1\}/, `${field} must allow any integer count`);
  }
});
