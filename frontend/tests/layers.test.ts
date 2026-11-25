import assert from "node:assert/strict";
import test from "node:test";
import { isLayerMuted, setLayerActive, summarizeLayers } from "../src/editor/layers.ts";

const notes = [
  { start: 0, end: 1, midi: 60, layer: "Lead" },
  { start: 0, end: 1, midi: 48, layer: "Bass" },
  { start: 1, end: 2, midi: 62, layer: "Lead" },
  { start: 2, end: 3, midi: 64 },
];

test("layers are listed in order of appearance with counts", () => {
  assert.deepEqual(summarizeLayers(notes), [
    { name: "Lead", label: "Lead", count: 2 },
    { name: "Bass", label: "Bass", count: 1 },
    { name: "", label: "レイヤーなし", count: 1 },
  ]);
});

test("muted layers include notes without a layer as an empty name", () => {
  assert.equal(isLayerMuted(notes[0], ["Lead"]), true);
  assert.equal(isLayerMuted(notes[1], ["Lead"]), false);
  assert.equal(isLayerMuted(notes[3], [""]), true);
  assert.equal(isLayerMuted(notes[0], undefined), false);
});

test("switching a layer on or off edits the muted list", () => {
  assert.deepEqual(setLayerActive([], "Bass", false), ["Bass"]);
  assert.deepEqual(setLayerActive(["Bass", "Lead"], "Bass", true), ["Lead"]);
  assert.deepEqual(setLayerActive(["Bass"], "Bass", false), ["Bass"]);
});
