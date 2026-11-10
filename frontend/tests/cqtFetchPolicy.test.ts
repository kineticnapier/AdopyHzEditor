import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { shouldFetchCqtSpectrum } from "../src/editor/cqtFetchPolicy.ts";

test("CQT requests are needed only when the CQT layer is visible", () => {
  for (const mode of ["spec", "both"] as const) {
    assert.equal(shouldFetchCqtSpectrum(true, "cqt", mode), true);
    assert.equal(shouldFetchCqtSpectrum(true, undefined, mode), true);
    assert.equal(shouldFetchCqtSpectrum(false, "cqt", mode), false);
    assert.equal(shouldFetchCqtSpectrum(true, "vorbis_direct", mode), false);
  }
  for (const source of ["cqt", "vorbis_direct", undefined]) {
    assert.equal(shouldFetchCqtSpectrum(true, source, "notes"), false);
  }
  assert.equal(shouldFetchCqtSpectrum(true, "cqt", "spec"), true);
  assert.equal(shouldFetchCqtSpectrum(true, "cqt", "notes"), false);
  assert.equal(shouldFetchCqtSpectrum(true, "cqt", "both"), true);
});

test("initial connection, document replacement, and delayed CQT refresh share the visibility guard", () => {
  const app = readFileSync(new URL("../src/App.tsx", import.meta.url), "utf8");
  assert.equal((app.match(/shouldFetchCqtSpectrum\(/g) ?? []).length, 3);
  assert.match(app, /if\s*\(shouldFetchCqtSpectrum\(state\.analysis\.available, state\.analysis\.source, state\.view\.mode\)\)\s*await refreshSpectrum\(backend, state\.view\)/);
  assert.match(app, /if\s*\(shouldFetchCqtSpectrum\(state\.analysis\.available, state\.analysis\.source, state\.view\.mode\)\)\s*await refreshSpectrum\(api, state\.view\);\s*else setSpectrum\(null\)/);
  assert.match(app, /if\s*\(!api \|\| !shouldFetchCqtSpectrum\(analysisAvailable, analysisSource, view\.mode\)\)\s*\{\s*setSpectrum\(null\);\s*return;/);
});
