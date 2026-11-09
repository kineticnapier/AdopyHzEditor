import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { blankWorkspaceDefaultsContextIsCurrent } from "../src/dialogs/previewFreshness.ts";

const css = readFileSync(new URL("../src/dialogs.css", import.meta.url), "utf8");
const help = readFileSync(new URL("../src/dialogs/HelpDialog.tsx", import.meta.url), "utf8");

test("help dialog retains a two-column navigation layout on wide windows", () => {
  assert.match(help, /className="modal-window help-window"/);
  assert.match(help, /className="help-layout"/);
  assert.match(help, /<nav aria-label="ヘルプ項目">/);
  assert.match(help, /<article\b/);
  assert.match(css, /\.help-layout\{[^}]*grid-template-columns:190px minmax\(0,1fr\)/);
});

test("narrow help dialog stacks scrollable navigation above readable article", () => {
  // At 320px viewport the 280px modal would otherwise devote 150px to nav,
  // leaving very little room for help text. Navigation must scroll sideways.
  const narrow = css.slice(css.lastIndexOf("@media(max-width:560px)"));
  assert.match(narrow, /\.help-layout\{[^}]*grid-template-columns:minmax\(0,1fr\)[^}]*grid-template-rows:auto minmax\(0,1fr\)/);
  assert.match(narrow, /\.help-layout nav\{[^}]*flex-direction:row[^}]*overflow-x:auto[^}]*overflow-y:hidden[^}]*min-width:0/);
  assert.match(narrow, /\.help-layout nav button\{[^}]*flex:none[^}]*white-space:nowrap/);
  assert.match(narrow, /\.help-layout article\{[^}]*min-height:0/);
});

test("changing help sections resets the article scroll position", () => {
  // A keyed article is remounted when the active section changes, instead of
  // preserving the previous section's scrollTop on the same DOM element.
  assert.match(help, /onClick=\{\(\) => setSection\(x\.id\)\}/);
  assert.match(help, /<article key=\{current\?\.id\}>/);
});

test("help loading and failure states are announced to assistive technology", () => {
  assert.match(help, /<div className="dialog-loading" role="status">ヘルプを読み込んでいます…<\/div>/);
  assert.match(help, /<div className="dialog-error" role="alert">ヘルプの読込に失敗しました:/);
});

test("help content and loading errors cannot survive API replacement or retry", () => {
  const api = {};
  const original = { api, attempt: 0 };
  assert.equal(blankWorkspaceDefaultsContextIsCurrent(original, original), true);
  assert.equal(blankWorkspaceDefaultsContextIsCurrent(original, { api: {}, attempt: 0 }), false);
  assert.equal(blankWorkspaceDefaultsContextIsCurrent(original, { api, attempt: 1 }), false);
  assert.equal(blankWorkspaceDefaultsContextIsCurrent(null, original), false);
  // The render-time guard is needed: effect cleanup alone runs after render.
  assert.match(help, /blankWorkspaceDefaultsContextIsCurrent\(payload, context\)/);
  assert.match(help, /blankWorkspaceDefaultsContextIsCurrent\(error, context\)/);
  assert.match(help, /setPayload\(\{ api, attempt, value \}\)/);
  assert.match(help, /setError\(\{ api, attempt, message: String\(reason\) \}\)/);
  assert.match(help, /currentError \?/);
  assert.match(help, /!currentPayload \?/);
  assert.match(help, /currentPayload\.sections\.map/);
});
