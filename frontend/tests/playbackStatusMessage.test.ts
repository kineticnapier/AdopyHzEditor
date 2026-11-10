import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { playbackStatusMessage, playbackToggleEnabled } from "../src/components/playbackStatusMessage.ts";

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
  assert.match(toolbar, /p\.connected \? playbackStatusMessage\(p\.playback, p\.hasPlayableContent\) : null/);
  assert.match(toolbar, /playbackStatus && <span className="playback-error" role="status" title=\{playbackStatus\}>/);
  assert.match(styles, /\.toolbar \.playback-error \{[^}]*text-overflow:ellipsis/);
});


test("empty workspace does not show an unavailable warning", () => {
  assert.equal(playbackStatusMessage({ available: false, error: null }, false), null);
  assert.equal(playbackStatusMessage({ available: false, error: " " }, false), null);
});

test("a real audio device error is still shown in an empty workspace", () => {
  assert.equal(
    playbackStatusMessage({ available: false, error: "  Device missing  " }, false),
    "再生エラー: Device missing",
  );
});

test("a workspace with notes or audio still reports unavailable playback", () => {
  assert.equal(playbackStatusMessage({ available: false, error: null }, true), "再生できません");
  const app = readFileSync(new URL("../src/App.tsx", import.meta.url), "utf8");
  assert.match(app, /hasPlayableContent=\{audioName !== null \|\| notes\.length > 0\}/);
});


test("disconnected preview disables no-op Play and Stop buttons", () => {
  const toolbar = readFileSync(new URL("../src/components/TopToolbar.tsx", import.meta.url), "utf8");
  // Without a Python bridge, App.togglePlayback and App.stopPlayback have no effect.
  assert.match(toolbar, /aria-label="停止"[^>]*disabled=\{!p\.connected\}[^>]*onClick=\{p\.onStop\}/);
  assert.match(toolbar, /aria-pressed=\{p\.playback\.playing\}[^>]*disabled=\{!playbackToggleEnabled\(p\.connected, p\.playback\)\}[^>]*onClick=\{p\.onPlay\}/);
  // Keep the locally functional seek-to-start action available in preview.
  assert.match(toolbar, /aria-label="先頭へ移動"[^>]*onClick=\{\(\)=>p\.onSeek\(0\)\}/);
});


test("Play is disabled for unavailable audio while Stop and Pause remain usable", () => {
  assert.equal(playbackToggleEnabled(false, { available: true, playing: false }), false);
  assert.equal(playbackToggleEnabled(true, { available: false, playing: false }), false);
  assert.equal(playbackToggleEnabled(true, { available: true, playing: false }), true);
  assert.equal(playbackToggleEnabled(true, { available: false, playing: true }), true);
  assert.equal(playbackToggleEnabled(false, { available: true, playing: true }), false);

  const toolbar = readFileSync(new URL("../src/components/TopToolbar.tsx", import.meta.url), "utf8");
  const app = readFileSync(new URL("../src/App.tsx", import.meta.url), "utf8");
  assert.match(toolbar, /disabled=\{!playbackToggleEnabled\(p\.connected, p\.playback\)\}/);
  assert.match(toolbar, /aria-label="停止"[^>]*disabled=\{!p\.connected\}/);
  assert.match(app, /if \(api && playbackToggleEnabled\(connected, playback\)\)/);
});
