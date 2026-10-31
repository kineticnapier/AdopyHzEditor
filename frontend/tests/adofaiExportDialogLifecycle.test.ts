import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { exportDefaultsContextIsCurrent } from "../src/dialogs/previewFreshness.ts";

const source = readFileSync(
  new URL("../src/dialogs/AdoFAIExportDialogJa.tsx", import.meta.url),
  "utf8",
);

test("selection refresh disables export until new defaults arrive", () => {
  const effectStart = source.indexOf("previewRequests.current.invalidate();");
  const loadStart = source.indexOf(".get_adofai_export_defaults(selected)", effectStart);
  assert.ok(effectStart >= 0 && loadStart > effectStart);
  const effect = source.slice(effectStart, loadStart);
  assert.match(effect, /setOptions\(null\)/);
  assert.ok(effect.indexOf("setOptions(null)") < loadStart - effectStart);
  assert.match(source, /if \(!options \|\| !defaultsCurrent\)\s*return\s*\(/);
  assert.match(source, /if \(alive\) \{\s*setLoadedContext\(/);
});

test("export and preview failures are announced to assistive technology", () => {
  assert.match(source, /\{error && <div className="dialog-error" role="alert">\{error\}<\/div>\}/);
  assert.match(source, /setError\(String\(e\)\)/);
});

test("selection refresh cannot unlock a still-running export", () => {
  const loadingStart = source.indexOf("if (!options || !defaultsCurrent)");
  const loadedStart = source.indexOf("const isHarmony", loadingStart);
  assert.ok(loadingStart >= 0 && loadedStart > loadingStart);
  const loading = source.slice(loadingStart, loadedStart);
  // The loading branch must preserve the same lock as the normal export form.
  assert.match(loading, /<Modal title="ADOFAI出力" onClose=\{onClose\} locked=\{working\}>/);
  assert.match(loading, /<button onClick=\{onClose\} disabled=\{working\}>閉じる<\/button>/);
  assert.match(loading, /className="primary"\s+disabled=\{working\}\s+onClick=\{\(\) => setLoadAttempt/);
  assert.match(loading, /className="dialog-loading" role="status"/);
  assert.match(loading, /working \? "出力処理中…"/);
});

test("defaults are invalid during render after selection, API, or retry changes", () => {
  const api = {};
  const selected = [1, 2];
  const context = { api, selected, defaultSelectedOnly: false, loadAttempt: 0, documentGeneration: 7 };
  assert.equal(exportDefaultsContextIsCurrent(context, context), true);
  assert.equal(exportDefaultsContextIsCurrent(context, { ...context, selected: [1, 2] }), false);
  assert.equal(exportDefaultsContextIsCurrent(context, { ...context, api: {} }), false);
  assert.equal(exportDefaultsContextIsCurrent(context, { ...context, defaultSelectedOnly: true }), false);
  assert.equal(exportDefaultsContextIsCurrent(context, { ...context, loadAttempt: 1 }), false);
  assert.equal(exportDefaultsContextIsCurrent(context, { ...context, documentGeneration: 8 }), false);
  assert.equal(exportDefaultsContextIsCurrent(null, context), false);
});

test("ADOFAI export guards rendering and action snapshots before effects", () => {
  assert.match(source, /const defaultsCurrent = exportDefaultsContextIsCurrent\(/);
  assert.match(source, /if \(!options \|\| !defaultsCurrent\)/);
  assert.match(source, /const fixed = options && defaultsCurrent/);
  assert.match(source, /setLoadedContext\(\{ api, selected, defaultSelectedOnly, loadAttempt, documentGeneration \}\)/);
  assert.match(source, /workingRef\.current \|\| !defaultsCurrent/);
});

test("ADOFAI export reloads after document replacement with the same selection", () => {
  const app = readFileSync(new URL("../src/App.tsx", import.meta.url), "utf8");
  assert.match(app, /<AdoFAIExportDialog[\s\S]*?documentGeneration=\{documentGeneration\.current\}/);
  assert.match(source, /\[api, selected, defaultSelectedOnly, loadAttempt, documentGeneration\]/);
});

test("late song-source chooser results cannot belong to a replacement document", async () => {
  const api = {};
  const selected = [1];
  const original = { api, selected, defaultSelectedOnly: true, loadAttempt: 0, documentGeneration: 5 };
  let latest = original;
  let complete!: (path: string) => void;
  const chooser = new Promise<string>((resolve) => { complete = resolve; });
  const accepted = chooser.then((path) =>
    exportDefaultsContextIsCurrent(original, latest) ? path : null,
  );
  // retainValidSelection can keep the same array even after document replacement.
  latest = { ...original, documentGeneration: 6 };
  complete("old-document.ogg");
  assert.equal(await accepted, null);

  // The same completion is valid if the request context has not changed.
  assert.equal(exportDefaultsContextIsCurrent(original, original), true);
  assert.equal(exportDefaultsContextIsCurrent(original, { ...original, selected: [1] }), false);
});

test("ADOFAI export actions recheck their original context after awaiting", () => {
  assert.match(source, /const latestRequestContext = useRef\(requestContext\)/);
  assert.match(source, /latestRequestContext\.current = requestContext/);
  assert.match(source, /function isCurrentAction\(context: typeof loadedContext\)/);
  const actions = [
    ["exportLevel", "tilePreview"],
    ["tilePreview", "debugPreview"],
    ["debugPreview", "chooseSongSource"],
    ["chooseSongSource", "if (!options || !defaultsCurrent)"],
  ];
  for (const [start, end] of actions) {
    const section = source.slice(
      source.indexOf(`async function ${start}()`),
      source.indexOf(end.startsWith("if (") ? end : `async function ${end}()`),
    );
    assert.match(section, /const context = loadedContext/);
    assert.match(section, /if \(!fixed \|\| !context\) return/);
    assert.match(section, /isCurrentAction\(context\)/);
  }
  const chooser = source.slice(source.indexOf("async function chooseSongSource()"));
  assert.match(chooser, /setOptions\(\(o\) =>\s*isCurrentAction\(context\) && o/);
  const run = source.slice(source.indexOf("async function run<"), source.indexOf("const fixed ="));
  assert.match(run, /if \(isCurrentAction\(context\)\) setError\(String\(e\)\)/);
});
