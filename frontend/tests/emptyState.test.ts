import assert from "node:assert/strict";
import test from "node:test";
import { shouldShowCanvasEmptyHint, workspaceTitle } from "../src/editor/emptyState.ts";
import { readFileSync } from "node:fs";

test("only a truly empty audio-less workspace shows the start hint", () => {
  assert.equal(shouldShowCanvasEmptyHint(null, 0), true);
  assert.equal(shouldShowCanvasEmptyHint(null, 1), false);
  assert.equal(shouldShowCanvasEmptyHint(null, 100), false);
  assert.equal(shouldShowCanvasEmptyHint("song.ogg", 0), false);
});

test("title bar distinguishes empty and notes-only workspaces", () => {
  assert.equal(workspaceTitle(null, false), "空のワークスペース");
  assert.equal(workspaceTitle(null, true), "ノートのみのワークスペース");
});

test("audio file name remains the title with or without notes", () => {
  assert.equal(workspaceTitle("song.ogg", false), "song.ogg");
  assert.equal(workspaceTitle("song.ogg", true), "song.ogg");
});

test("title bar uses the same content flag as the playback warning", () => {
  const toolbar = readFileSync(new URL("../src/components/TopToolbar.tsx", import.meta.url), "utf8");
  assert.match(toolbar, /workspaceTitle\(p\.audioName,p\.hasPlayableContent\)/);
});
