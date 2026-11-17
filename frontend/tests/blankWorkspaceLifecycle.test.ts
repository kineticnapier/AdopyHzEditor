import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { blankWorkspaceDefaultsContextIsCurrent, blankWorkspaceMidiRangeIsValid } from "../src/dialogs/previewFreshness.ts";

const source = readFileSync(
  new URL("../src/dialogs/ToolDialogs.tsx", import.meta.url),
  "utf8",
);
const blank = source.slice(
  source.indexOf("export function BlankWorkspaceDialog("),
  source.indexOf("export function HarmonicDiagramDialog("),
);

test("blank workspace defaults belong to the exact API and retry", () => {
  const api = {};
  const loaded = { api, attempt: 0 };
  assert.equal(blankWorkspaceDefaultsContextIsCurrent(loaded, loaded), true);
  assert.equal(blankWorkspaceDefaultsContextIsCurrent(loaded, { api: {}, attempt: 0 }), false);
  assert.equal(blankWorkspaceDefaultsContextIsCurrent(loaded, { api, attempt: 1 }), false);
  assert.equal(blankWorkspaceDefaultsContextIsCurrent(null, loaded), false);
});

test("blank workspace hides stale defaults before effects and blocks apply", () => {
  assert.match(blank, /const defaultsCurrent = blankWorkspaceDefaultsContextIsCurrent\(loadedContext, requestContext\)/);
  assert.match(blank, /setValue\(null\)/);
  assert.match(blank, /setLoadedContext\(null\)/);
  assert.match(blank, /setLoadedContext\(\{ api, attempt \}\)/);
  assert.match(blank, /\[api, attempt\]/);
  assert.match(blank, /value && defaultsCurrent \?/);
  assert.match(blank, /if \(!value \|\| !defaultsCurrent \|\| applying \|\| !midiRangeValid\) return/);
  assert.match(blank, /disabled=\{!value \|\| !defaultsCurrent \|\| applying \|\| !midiRangeValid\}/);
  assert.match(blank, /onChange=\{\(v\) => patchValue\(\{ duration: v \}\)\}/);
});

test("blank workspace retries hide stale errors and cannot retry while applying", () => {
  assert.match(blank, /blankWorkspaceDefaultsContextIsCurrent\(loadError, requestContext\)/);
  assert.match(blank, /setLoadError\(\{ message: String\(e\), api, attempt \}\)/);
  assert.match(blank, /error=\{currentLoadError\}/);
  assert.match(blank, /disabled=\{applying\}/);
  assert.match(blank, /className="dialog-loading" role="status"/);
});

test("blank workspace does not close or report an obsolete apply after an API change", async () => {
  assert.match(blank, /const latestRequestContext = useRef\(requestContext\)/);
  assert.match(blank, /latestRequestContext\.current = requestContext/);
  const apply = blank.slice(blank.indexOf("async function apply()"), blank.indexOf("  return (", blank.indexOf("async function apply()")));
  assert.match(apply, /await onApply\(snapshot\);\s*if \(!blankWorkspaceDefaultsContextIsCurrent\(loadedContext, latestRequestContext\.current\)\) return;/);
  assert.match(apply, /catch \(e\) \{\s*if \(blankWorkspaceDefaultsContextIsCurrent\(loadedContext, latestRequestContext\.current\)\) onStatus\(String\(e\)\);/);

  const original = { api: {}, attempt: 0 };
  let current = original;
  let finish!: () => void;
  const delayed = new Promise<void>(resolve => { finish = resolve; });
  const completion = delayed.then(() => blankWorkspaceDefaultsContextIsCurrent(original, current));
  current = { api: {}, attempt: 0 };
  finish();
  assert.equal(await completion, false);
});

test("blank workspace prevents silent normalization of invalid MIDI bounds", () => {
  assert.equal(blankWorkspaceMidiRangeIsValid({ midiMin: 0, midiMax: 127 }), true);
  assert.equal(blankWorkspaceMidiRangeIsValid({ midiMin: 60, midiMax: 61 }), true);
  for (const invalid of [
    null,
    { midiMin: 60, midiMax: 60 },
    { midiMin: 120, midiMax: 12 },
    { midiMin: 127, midiMax: 127 },
    { midiMin: -1, midiMax: 120 },
    { midiMin: 0, midiMax: 128 },
    { midiMin: 0.5, midiMax: 120 },
    { midiMin: Number.NaN, midiMax: 120 },
  ]) {
    assert.equal(blankWorkspaceMidiRangeIsValid(invalid), false);
  }
  assert.match(blank, /const midiRangeValid = blankWorkspaceMidiRangeIsValid\(value\)/);
  assert.match(blank, /role="alert">\s*最低MIDIは最高MIDIより小さくしてください。/);
  assert.match(blank, /disabled=\{!value \|\| !defaultsCurrent \|\| applying \|\| !midiRangeValid\}/);
});
