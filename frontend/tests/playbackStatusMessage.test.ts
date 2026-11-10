import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { playbackStatusMessage } from "../src/components/playbackStatusMessage.ts";

test("available playback without an error needs no warning", () => {
  assert.equal(playbackStatusMessage({ available: true, error: null }), null);
});

test("unavailable playback is visible even without a device error string", () => {
  assert.equal(playbackStatusMessage({ available: false, error: null }), "再生できません");
});

test("device errors are shown even if an older availability flag was true", () => {
  assert.equal(
    playbackStatusMessage({ available: true, error: "  PortAudio device unavailable  " }),
    "再生エラー: PortAudio device unavailable",
  );
});

test("empty error strings do not hide the unavailable state", () => {
  assert.equal(playbackStatusMessage({ available: false, error: "  " }), "再生できません");
  assert.equal(playbackStatusMessage({ available: true, error: "" }), null);
});

test("toolbar displays the backend error in a named status without affecting browser preview", () => {
  const toolbar = readFileSync(new URL("../src/components/TopToolbar.tsx", import.meta.url), "utf8");
  const styles = readFileSync(new URL("../src/styles.css", import.meta.url), "utf8");
  assert.match(toolbar, /p\.connected \? playbackStatusMessage\(p\.playback\) : null/);
  assert.match(toolbar, /playbackStatus && <span className="playback-error" role="status" title=\{playbackStatus\}>/);
  assert.match(styles, /\.toolbar \.playback-error \{[^}]*text-overflow:ellipsis/);
});
