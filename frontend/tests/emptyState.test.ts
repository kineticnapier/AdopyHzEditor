import assert from "node:assert/strict";
import test from "node:test";
import { shouldShowCanvasEmptyHint } from "../src/editor/emptyState.ts";

test("only a truly empty audio-less workspace shows the start hint", () => {
  assert.equal(shouldShowCanvasEmptyHint(null, 0), true);
  assert.equal(shouldShowCanvasEmptyHint(null, 1), false);
  assert.equal(shouldShowCanvasEmptyHint(null, 100), false);
  assert.equal(shouldShowCanvasEmptyHint("song.ogg", 0), false);
});
