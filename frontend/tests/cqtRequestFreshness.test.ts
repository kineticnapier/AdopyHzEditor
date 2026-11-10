import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { LatestRequestGate } from "../src/api/requestCoordinator.ts";

test("a CQT response from the old viewport cannot apply during the refresh debounce", async () => {
  const gate = new LatestRequestGate();
  const displayed: string[] = [];
  let finishOld!: (value: string) => void;
  const oldPayload = new Promise<string>(resolve => { finishOld = resolve; });
  const oldRequest = gate.issue();
  const pending = oldPayload.then(payload => {
    if (gate.isCurrent(oldRequest)) displayed.push(payload);
  });

  // The view changes while the next get_spectrogram call is still debounced.
  gate.invalidate();
  finishOld("obsolete CQT");
  await pending;
  assert.deepEqual(displayed, []);

  const newRequest = gate.issue();
  if (gate.isCurrent(newRequest)) displayed.push("current CQT");
  assert.deepEqual(displayed, ["current CQT"]);
});

test("CQT view and analysis changes invalidate old replies before the delayed fetch", () => {
  const app = readFileSync(new URL("../src/App.tsx", import.meta.url), "utf8");
  const guardStart = app.indexOf("  // CQT requests are debounced by 140 ms below.");
  const delayedFetch = app.indexOf("  useEffect(() => {", guardStart);
  assert.ok(guardStart >= 0 && delayedFetch > guardStart, "missing immediate CQT invalidation");
  const guard = app.slice(guardStart, delayedFetch);
  assert.match(guard, /useLayoutEffect\(\(\) => \{\s*spectrumRequests\.current\.invalidate\(\);\s*\}, \[/);
  for (const dependency of [
    "api", "analysisAvailable", "analysisSource",
    "settings.contrast", "settings.gamma", "settings.enhance",
    "settings.displayMode", "settings.harmonics",
    "view.mode", "view.start", "view.windowSeconds",
    "view.pitchBottom", "view.visibleNotes",
  ]) {
    assert.ok(guard.includes(dependency), `CQT request not invalidated for ${dependency}`);
  }
  const effect = app.slice(delayedFetch, app.indexOf("  useLayoutEffect(() => {", delayedFetch));
  assert.match(effect, /window\.setTimeout\(\(\) => void refreshSpectrum\(api, view\), 140\)/);
  assert.match(effect, /setSpectrum\(null\)/);
});
