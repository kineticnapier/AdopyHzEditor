import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { harmonicDefaultsContextIsCurrent, selectionScopedPreviewIsCurrent } from "../src/dialogs/previewFreshness.ts";

const source = readFileSync(
  new URL("../src/dialogs/ToolDialogs.tsx", import.meta.url),
  "utf8",
);
const harmonic = source.slice(source.indexOf("export function HarmonicDiagramDialog("), source.indexOf("export function UpdateDialog("));

test("selection changes invalidate harmonic defaults and the previous preview before loading", () => {
  const effect = harmonic.slice(harmonic.indexOf("useEffect(() => {"), harmonic.indexOf("}, [api, selected, attempt, documentGeneration]);"));
  const request = effect.indexOf("api.get_harmonic_diagram_defaults(selected)");
  assert.ok(request > 0, "defaults request must be present");
  for (const reset of ["setOpts(null)", "setDefaultsSelectionKey(null)", "setPreview(null)", 'setPreviewKey("")']) {
    const index = effect.indexOf(reset);
    assert.ok(index >= 0 && index < request, `${reset} must precede the defaults request`);
  }
  assert.match(harmonic, /if\(!previewCurrent\)/);
});

test("selection refresh does not unlock a pending harmonic insertion", () => {
  const loading = harmonic.slice(harmonic.indexOf("if (!opts && error)"), harmonic.indexOf("return (\n    <Modal title=\"倍音ダイアグラム\" onClose={onClose} wide"));
  assert.match(loading, /<Modal title="倍音ダイアグラム" onClose=\{onClose\} locked=\{inserting\}>/g);
  assert.equal((loading.match(/locked=\{inserting\}/g) ?? []).length, 2);
  assert.match(loading, /<LoadFailure[^\n]*disabled=\{inserting\}/);
  assert.match(loading, /className="dialog-loading" role="status"/);
  assert.match(loading, /inserting \? "挿入処理中…"/);
  assert.match(source, /function LoadFailure\(\{ error, onRetry, disabled = false \}/);
  assert.match(source, /<button className="primary" onClick=\{onRetry\} disabled=\{disabled\}>/);
});


test("harmonic preview stays stale after a selection change even when options match", () => {
  const preview = { rows: [] };
  assert.equal(selectionScopedPreviewIsCurrent(preview, "options", "options", "[1,2]", "[1,2]"), true);
  assert.equal(selectionScopedPreviewIsCurrent(preview, "options", "options", "[1,2]", "[2,3]"), false);
  assert.equal(selectionScopedPreviewIsCurrent(preview, "options", "options", null, "[1,2]"), false);
  assert.equal(selectionScopedPreviewIsCurrent(preview, "old", "options", "[1,2]", "[1,2]"), false);
  assert.equal(selectionScopedPreviewIsCurrent(null, "options", "options", "[1,2]", "[1,2]"), false);
});

test("harmonic dialog hides old defaults before its selection effect can run", () => {
  assert.match(harmonic, /const selectionKey = JSON\.stringify\(selected\)/);
  assert.match(harmonic, /const selectionCurrent = defaultsSelectionKey === selectionKey/);
  assert.match(harmonic, /if \(!opts \|\| !selectionCurrent\)/);
  assert.match(harmonic, /setDefaultsSelectionKey\(selectionKey\)/);
  assert.match(harmonic, /selectionScopedPreviewIsCurrent\(preview, previewKey/);
});

test("same note IDs from another document cannot reuse harmonic defaults", () => {
  const api = {};
  const selected = [3, 5];
  const loaded = { api, selected, attempt: 0, documentGeneration: 7 };
  assert.equal(harmonicDefaultsContextIsCurrent(loaded, loaded), true);
  assert.equal(harmonicDefaultsContextIsCurrent(loaded, { ...loaded, selected: [3, 5] }), false);
  assert.equal(harmonicDefaultsContextIsCurrent(loaded, { ...loaded, api: {} }), false);
  assert.equal(harmonicDefaultsContextIsCurrent(loaded, { ...loaded, attempt: 1 }), false);
  assert.equal(harmonicDefaultsContextIsCurrent(loaded, { ...loaded, documentGeneration: 8 }), false);
  assert.equal(harmonicDefaultsContextIsCurrent(null, loaded), false);
});

test("harmonic dialog blocks stale defaults, preview, insertion and delayed numeric blur", () => {
  assert.match(harmonic, /harmonicDefaultsContextIsCurrent\(defaultsContext, \{ api, selected, attempt, documentGeneration \}\)/);
  assert.match(harmonic, /setDefaultsContext\(null\)/);
  assert.match(harmonic, /setDefaultsContext\(\{ api, selected, attempt, documentGeneration \}\)/);
  assert.match(harmonic, /const previewCurrent = selectionCurrent &&/);
  assert.match(harmonic, /if \(!opts \|\| !selectionCurrent\) return;/);
  assert.match(harmonic, /if \(!insertingRef.current && selectionCurrent\) setOpts\(next\)/);
});

test("harmonic dialog reloads on document changes even if selection reference stays stable", () => {
  const app = readFileSync(new URL("../src/App.tsx", import.meta.url), "utf8");
  assert.match(app, /<HarmonicDiagramDialog[\s\S]*?documentGeneration=\{documentGeneration\.current\}/);
  assert.match(harmonic, /\[api, selected, attempt, documentGeneration\]/);
});
