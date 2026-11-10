import assert from "node:assert/strict";
import test from "node:test";
import { formatPlaybackTime } from "../src/components/formatPlaybackTime.ts";

test("playback clock renders minutes and rounds milliseconds across boundaries", () => {
  assert.equal(formatPlaybackTime(0), "0:00.000");
  assert.equal(formatPlaybackTime(61.234), "1:01.234");
  assert.equal(formatPlaybackTime(59.9996), "1:00.000");
  assert.equal(formatPlaybackTime(3600), "60:00.000");
});

test("playback clock clamps negative finite times without negative digits", () => {
  assert.equal(formatPlaybackTime(-1), "0:00.000");
  assert.equal(formatPlaybackTime(-0.0002), "0:00.000");
});

test("playback clock shows unknown instead of fabricated zero or NaN/Infinity", () => {
  for (const seconds of [NaN, Infinity, -Infinity, Number.MAX_VALUE]) {
    assert.equal(formatPlaybackTime(seconds), "--:--.---");
  }
});
