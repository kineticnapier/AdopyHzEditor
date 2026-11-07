import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { trackPrimitiveIntersectsViewport } from "../src/editor/editorMath.ts";

test("offscreen Frequency Track points do not need canvas drawing", () => {
  assert.equal(trackPrimitiveIntersectsViewport(50, 50, 50, 50, 100, 100), true);
  assert.equal(trackPrimitiveIntersectsViewport(-9, 50, -9, 50, 100, 100), false);
  assert.equal(trackPrimitiveIntersectsViewport(109, 50, 109, 50, 100, 100), false);
  assert.equal(trackPrimitiveIntersectsViewport(50, -9, 50, -9, 100, 100), false);
  assert.equal(trackPrimitiveIntersectsViewport(50, 109, 50, 109, 100, 100), false);
});

test("segments crossing the viewport remain visible even with both endpoints outside", () => {
  assert.equal(trackPrimitiveIntersectsViewport(-100, 50, 200, 50, 100, 100), true);
  assert.equal(trackPrimitiveIntersectsViewport(-100, -100, 200, 200, 100, 100), true);
  assert.equal(trackPrimitiveIntersectsViewport(-100, -50, 200, -30, 100, 100), false);
});

test("the stroke margin retains edge points and rejects invalid geometry", () => {
  assert.equal(trackPrimitiveIntersectsViewport(-8, 50, -8, 50, 100, 100), true);
  assert.equal(trackPrimitiveIntersectsViewport(108, 50, 108, 50, 100, 100), true);
  assert.equal(trackPrimitiveIntersectsViewport(Number.NaN, 0, 0, 0, 100, 100), false);
  assert.equal(trackPrimitiveIntersectsViewport(0, 0, Infinity, 0, 100, 100), false);
  assert.equal(trackPrimitiveIntersectsViewport(0, 0, 0, 0, 0, 100), false);
});

test("Track viewport rejection occurs before Canvas draw commands", () => {
  const source = readFileSync(new URL("../src/editor/EditorCanvas.tsx", import.meta.url), "utf8");
  const start = source.indexOf("for(let i=0;i<decodedTracks.count;i+=1)");
  assert.ok(start >= 0);
  const end = source.indexOf("ctx.restore();", start);
  assert.ok(end > start);
  const loop = source.slice(start, end);
  const rejection = loop.indexOf("trackPrimitiveIntersectsViewport(");
  assert.ok(rejection >= 0);
  assert.ok(rejection < loop.indexOf("ctx.beginPath()"));
});
