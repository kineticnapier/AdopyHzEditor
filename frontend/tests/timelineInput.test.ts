import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { commitNumericEdit } from "../src/settings/numericInputModel.ts";

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
