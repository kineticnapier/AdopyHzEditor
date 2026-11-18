import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const toolbar = readFileSync(new URL("../src/components/TopToolbar.tsx", import.meta.url), "utf8");

test("rapidly changing playback time is not an automatic live announcement", () => {
  // <output> has an implicit status role, so its live behavior must be explicitly disabled.
  assert.match(toolbar, /<output aria-live="off" aria-label="再生位置と総再生時間">/);
  assert.match(toolbar, /formatPlaybackTime\(p\.playback\.time\)/);
  assert.match(toolbar, /formatPlaybackTime\(p\.playback\.duration\)/);
});

test("playback errors remain available as an announced status", () => {
  assert.match(toolbar, /playbackStatus && <span className="playback-error" role="status"/);
});
