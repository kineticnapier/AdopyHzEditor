import assert from "node:assert/strict";
import test from "node:test";
import { readFileSync } from "node:fs";
import { isDialogCompositionKey } from "../src/dialogs/dialogFocus.ts";
import { commitNumericEdit } from "../src/settings/numericInputModel.ts";

test("timeline numeric inputs defer Enter and Escape during IME composition", () => {
  assert.equal(isDialogCompositionKey({ isComposing: true, keyCode: 13 }), true);
  assert.equal(isDialogCompositionKey({ isComposing: true, keyCode: 27 }), true);
  assert.equal(isDialogCompositionKey({ isComposing: false, keyCode: 229 }), true);
  assert.equal(isDialogCompositionKey({ isComposing: false, keyCode: 13 }), false);
});

test("timeline numeric field checks IME before Enter/Escape and contains keyboard events", () => {
  const source = readFileSync(new URL("../src/editor/Timeline.tsx", import.meta.url), "utf8")
    .replace(/\r\n/g, "\n");
  const start = source.indexOf("function CommitNumber(");
  assert.ok(start >= 0, "timeline numeric component exists");
  const field = source.slice(start);
  const composition = field.indexOf("if (isDialogCompositionKey(event.nativeEvent)) return;");
  const enter = field.indexOf('if (event.key === "Enter")');
  const escape = field.indexOf('else if (event.key === "Escape")');
  assert.ok(composition >= 0 && composition < enter && enter < escape,
    "IME check must run before numeric Enter/Escape handlers");
  assert.match(field.slice(enter, escape), /event\.preventDefault\(\);[\s\S]*event\.stopPropagation\(\);[\s\S]*event\.currentTarget\.blur\(\)/,
    "Enter commits without leaking into parent keyboard handlers");
  assert.match(field.slice(escape), /event\.preventDefault\(\);[\s\S]*event\.stopPropagation\(\);[\s\S]*cancelledRef\.current = true/,
    "Escape cancels without triggering parent shortcuts");
});

// Bridge.set_view uses Python _int_clamp for pitchBottom and visibleNotes.
test("timeline whole-step pitch inputs round before calling set_view", () => {
  assert.equal(commitNumericEdit("12.4", 12, 0, 127, false, true), 12);
  assert.equal(commitNumericEdit("12.6", 12, 0, 127, false, true), 13);
  assert.equal(commitNumericEdit("12.5", 12, 0, 127, false, true), 12);
  assert.equal(commitNumericEdit("13.5", 12, 0, 127, false, true), 14);
  assert.equal(commitNumericEdit("127.6", 120, 0, 127, false, true), 127);
  assert.equal(commitNumericEdit("13.5", 12, 0, 127, true, true), 12);
  assert.equal(commitNumericEdit("1.25", 1, 0.2, 60, false, false), 1.25);
});

test("timeline uses integer normalization only for step-one pitch fields", () => {
  const source = readFileSync(new URL("../src/editor/Timeline.tsx", import.meta.url), "utf8").replace(/\r\n/g, "\n");
  const component = source.slice(source.indexOf("function CommitNumber("));
  assert.match(component, /commitNumericEdit\(text, value, min, max, cancelledRef\.current, step === 1, editedRef\.current\)/);
  assert.match(source, /label="時間の表示幅"[^\n]*step="any"/);
  assert.match(source, /label="下端音高"[^\n]*step=\{1\}/);
  assert.match(source, /label="上端音高"[^\n]*step=\{1\}/);
});

test("an untouched timeline input keeps the latest external viewport value", () => {
  // Focus at 60, then a wheel/slider changes the backend view to 62.
  // Blur must keep 62, rather than replaying the original input text "60".
  assert.equal(commitNumericEdit("60", 62, 0, 127, false, true, false), 62);
  // An actual user edit still wins, with the existing integer normalization.
  assert.equal(commitNumericEdit("61.5", 62, 0, 127, false, true, true), 62);
  assert.equal(commitNumericEdit("63.5", 62, 0, 127, false, true, true), 64);
  assert.equal(commitNumericEdit("63.5", 62, 0, 127, true, true, true), 62);
});

test("timeline tracks focus and user edits before committing or syncing props", () => {
  const source = readFileSync(new URL("../src/editor/Timeline.tsx", import.meta.url), "utf8");
  const component = source.slice(source.indexOf("function CommitNumber("));
  assert.match(component, /const editingRef = useRef\(false\)/);
  assert.match(component, /const editedRef = useRef\(false\)/);
  assert.match(component, /if \(!editingRef\.current\) setText\(String\(value\)\)/);
  assert.match(component, /onFocus=\{\(\) => \{[^}]*editingRef\.current = true; editedRef\.current = false;/);
  assert.match(component, /onChange=\{\(event\) => \{ editedRef\.current = true; setText\(event\.target\.value\); \}\}/);
  assert.match(component, /editingRef\.current = false;[\s\S]*?editedRef\.current = false;/);
});


test("pitch viewport shared rounding import resolves under native Node TypeScript tests", () => {
  const source = readFileSync(new URL("../src/editor/pitchViewport.ts", import.meta.url), "utf8");
  assert.match(source, /from "\.\.\/settings\/numericInputModel\.ts"/,
    "Node's TypeScript type stripping requires an explicit .ts extension");
  const tsconfig = JSON.parse(readFileSync(new URL("../tsconfig.json", import.meta.url), "utf8"));
  assert.equal(tsconfig.compilerOptions.noEmit, true);
  assert.equal(tsconfig.compilerOptions.allowImportingTsExtensions, true);
});


test("timeline accepts fractional zoom widths returned by the view API", () => {
  const source = readFileSync(new URL("../src/editor/Timeline.tsx", import.meta.url), "utf8")
    .replace(/\r\n/g, "\n");
  // A zoom result such as 1.25 s is legal in the backend but is not on
  // the old HTML step grid: min 0.2 + n * 0.1.
  assert.equal((1.25 - 0.2) / 0.1, 10.5);
  assert.equal(commitNumericEdit("1.25", 1, 0.2, 60, false, false), 1.25);
  assert.match(source, /label="時間の表示幅"[^\n]*step="any"/);
  assert.match(source, /step:number \| "any";onCommit\(value:number\):void/);
});

test("timeline slider preserves sub-step viewport positions", () => {
  const source = readFileSync(new URL("../src/editor/Timeline.tsx", import.meta.url), "utf8")
    .replace(/\r\n/g, "\n");
  // The old dynamic step max/1000 rounded legitimate backend positions.
  const maxStart = 5;
  const backendStart = 1.234567;
  const oldStep = maxStart / 1000;
  assert.notEqual(Math.round(backendStart / oldStep) * oldStep, backendStart);
  assert.match(source, /className="timeline-slider"[^\n]*type="range"/);
  assert.match(source, /max=\{max > 0 \? max : \.001\} step="any"/);
  assert.match(source, /value=\{sliderValue\}/);
  assert.match(source, /timelineSliderBounds\(playback\.duration, view\.windowSeconds, view\.start\)/);
});
