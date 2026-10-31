import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const source = readFileSync(
  new URL("../src/dialogs/ToolDialogs.tsx", import.meta.url),
  "utf8",
);
const harmonic = source.slice(source.indexOf("export function HarmonicDiagramDialog("), source.indexOf("export function UpdateDialog("));

test("selection changes invalidate harmonic defaults and the previous preview before loading", () => {
  const effect = harmonic.slice(harmonic.indexOf("useEffect(() => {"), harmonic.indexOf("}, [api, selected, attempt]);"));
  const request = effect.indexOf("api.get_harmonic_diagram_defaults(selected)");
  assert.ok(request > 0, "defaults request must be present");
  for (const reset of ["setOpts(null)", "setPreview(null)", 'setPreviewKey("")']) {
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
