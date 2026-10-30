import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { commitNumericEdit } from "../src/settings/numericInputModel.ts";
import { timelineSliderStart } from "../src/editor/timelineNavigation.ts";

test("Timeline Escape cancels a pending edit even when blur sees stale text", () => {
  const original = 12;
  assert.equal(commitNumericEdit("6", original, 0.2, 120, true), original);
  assert.equal(commitNumericEdit("75", 60, 0, 127, true), 60);
  assert.equal(commitNumericEdit("108", 72, 6, 128, true), 72);
});

test("Timeline Enter and ordinary blur commit, but empty input keeps the value", () => {
  assert.equal(commitNumericEdit("6.5", 12, 0.2, 120, false), 6.5);
  assert.equal(commitNumericEdit("130", 60, 0, 127, false), 127);
  assert.equal(commitNumericEdit("", 12, 0.2, 120, false), 12);
});

test("Timeline connects Escape cancellation to the synchronous blur path", () => {
  const source = readFileSync(new URL("../src/editor/Timeline.tsx", import.meta.url), "utf8");
  assert.match(source, /const cancelledRef = useRef\(false\)/);
  assert.match(source, /commitNumericEdit\(text, value, min, max, cancelledRef\.current\)/);
  assert.match(source, /cancelledRef\.current = false;/);
  assert.match(source, /onBlur=\{commit\}/);
  assert.match(source, /event\.key === "Escape"[\s\S]*?cancelledRef\.current = true;[\s\S]*?event\.currentTarget\.blur\(\)/);
});

test("Timeline slider cannot change the view when the entire chart fits", () => {
  assert.equal(timelineSliderStart(.001, 0, 0), null);
  assert.equal(timelineSliderStart(0, 0, 0), null);
});

test("Timeline slider clamps out-of-range input and ignores unchanged positions", () => {
  assert.equal(timelineSliderStart(3, 3, 20), null);
  assert.equal(timelineSliderStart(25, 3, 20), 20);
  assert.equal(timelineSliderStart(-4, 3, 20), 0);
});

test("Timeline slider supports sub-millisecond scroll ranges", () => {
  assert.equal(timelineSliderStart(.001, 0, .0005), .0005);
  assert.equal(timelineSliderStart(.00025, 0, .0005), .00025);
  assert.equal(timelineSliderStart(.0005, .0005, .0005), null);
});

test("Timeline slider rejects invalid values and disables an immovable thumb", () => {
  assert.equal(timelineSliderStart(NaN, 1, 5), null);
  assert.equal(timelineSliderStart(Infinity, 1, 5), null);
  assert.equal(timelineSliderStart(2, 1, NaN), null);
  const source = readFileSync(new URL("../src/editor/Timeline.tsx", import.meta.url), "utf8");
  assert.match(source, /disabled=\{max <= 0\}/);
  assert.match(source, /timelineSliderStart\(Number\(e\.target\.value\), view\.start, max\)/);
  assert.match(source, /if \(start !== null\) onView\(\{ start \}\)/);
});
