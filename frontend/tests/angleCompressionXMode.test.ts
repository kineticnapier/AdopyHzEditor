import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { isXModeAvailable, xModeForCompression } from "../src/dialogs/angleCompressionXMode.ts";

test("fixed angle does not silently retain an ignored target-BPM X mode", () => {
  assert.equal(xModeForCompression("fixed", "target_bpm"), "floor");
  assert.equal(xModeForCompression("auto", "target_bpm"), "target_bpm");
  for (const xMode of ["floor", "lowest_floor", "round", "ceil", "fixed"] as const) {
    assert.equal(xModeForCompression("fixed", xMode), xMode);
  }
  assert.equal(isXModeAvailable("fixed", "target_bpm"), false);
  assert.equal(isXModeAvailable("auto", "target_bpm"), true);
  assert.equal(isXModeAvailable("fixed", "floor"), true);
});

test("ADOFAI dialog normalizes X mode when fixed compression is selected", () => {
  const source = readFileSync(new URL("../src/dialogs/AdoFAIExportDialogJa.tsx", import.meta.url), "utf8");
  assert.match(source, /onChange=\{\(v\) =>\s*changeAngleCompressionMode\(/);
  assert.match(source, /xMode: xModeForCompression\(angleCompressionMode, o\.xMode\)/);
  assert.match(source, /xModeOptions\.filter\(\(\[mode\]\) =>\s*isXModeAvailable\(options\.angleCompressionMode, mode\)\s*\)/);
});
