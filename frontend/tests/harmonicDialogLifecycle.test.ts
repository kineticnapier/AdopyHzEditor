import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { documentActionIsCurrent, harmonicDefaultsContextIsCurrent, selectionScopedPreviewIsCurrent } from "../src/dialogs/previewFreshness.ts";

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
  const loading = harmonic.slice(harmonic.indexOf("if (!opts && currentError)"), harmonic.indexOf("return (\n    <Modal title=\"倍音ダイアグラム\" onClose={onClose} wide"));
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
  assert.match(harmonic, /if \(!insertingRef.current && selectionCurrent\) \{\s*setError\(null\);\s*setOpts\(next\);\s*\}/);
});

test("harmonic dialog reloads on document changes even if selection reference stays stable", () => {
  const app = readFileSync(new URL("../src/App.tsx", import.meta.url), "utf8");
  assert.match(app, /<HarmonicDiagramDialog[\s\S]*?documentGeneration=\{documentGeneration\.current\}/);
  assert.match(harmonic, /\[api, selected, attempt, documentGeneration\]/);
});

test("harmonic errors are scoped to the active API, selection, retry and document", () => {
  const api = {};
  const selected = [3, 5];
  const context = { api, selected, attempt: 0, documentGeneration: 7 };
  assert.equal(harmonicDefaultsContextIsCurrent(context, context), true);
  for (const stale of [
    { ...context, api: {} },
    { ...context, selected: [3, 5] },
    { ...context, attempt: 1 },
    { ...context, documentGeneration: 8 },
  ]) {
    assert.equal(harmonicDefaultsContextIsCurrent(context, stale), false);
  }
  // Errors from defaults loading, preview and insertion must all carry their source.
  assert.match(harmonic, /const currentError = harmonicDefaultsContextIsCurrent\(error, \{ api, selected, attempt, documentGeneration \}\)/);
  assert.match(harmonic, /setError\(\{ message: String\(reason\), api, selected, attempt, documentGeneration \}\)/);
  assert.match(harmonic, /setError\(\{ message: String\(e\), api, selected, attempt, documentGeneration, optionsKey: requestedKey \}\)/);
  assert.match(harmonic, /setError\(\{ message: String\(e\), api, selected, attempt, documentGeneration, optionsKey: JSON\.stringify\(opts\) \}\)/);
  assert.match(harmonic, /harmonicErrorIsCurrent\(error, opts \? JSON\.stringify\(opts\) : null\)/);
  assert.match(harmonic, /if \(!opts && currentError\)/);
  assert.match(harmonic, /<LoadFailure error=\{currentError\}/);
  assert.match(harmonic, /\{currentError && <div className="dialog-error inline"/);
  assert.match(harmonic, /\{currentError \? "プレビューを表示できません"/);
  // Do not start a preview using the previous selection's options.
  assert.match(harmonic, /if \(!opts \|\| !selectionCurrent\) return;/);
  assert.match(harmonic, /\[api, opts, selected, attempt, documentGeneration, selectionCurrent\]/);
});

test("harmonic insertion completion ignores selection updates but not document or API replacement", () => {
  const api = {};
  const started = { api, documentGeneration: 7 };
  const selectionUpdated = { ...started, selected: [99] };
  assert.equal(documentActionIsCurrent(started, selectionUpdated), true);
  assert.equal(documentActionIsCurrent(started, { api: {}, documentGeneration: 7 }), false);
  assert.equal(documentActionIsCurrent(started, { api, documentGeneration: 8 }), false);
  const insertion = harmonic.slice(harmonic.indexOf("async function insert()"), harmonic.indexOf("if (!opts && currentError)"));
  assert.match(insertion, /const startedDocument = \{ api, documentGeneration \}/);
  assert.match(insertion, /if \(!documentActionIsCurrent\(startedDocument, latestDocumentContext\.current\)\) return;\s*onStatus\(r\.status\);\s*onClose\(\);/);
  assert.match(insertion, /catch \(e\) \{\s*if \(documentActionIsCurrent\(startedDocument, latestDocumentContext\.current\)\)/);
});
