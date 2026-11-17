import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { buildNoteTimeIndex, noteIntersects, regionSelectedNoteIndices } from "../src/editor/editorMath.ts";

test("region selection retains original note-index order and inclusive boundaries", () => {
  const notes = [
    { start: 9, end: 10, midi: 60 },
    { start: 1, end: 3, midi: 60 },
    { start: 2, end: 4, midi: 90 },
    { start: 2, end: 2.5, midi: 60, kind: "curve" as const, midi_end: 72, ctrl1_midi: 72, ctrl2_midi: 72 },
    { start: 4, end: 6, midi: 60 },
  ];
  const index = buildNoteTimeIndex(notes);
  assert.deepEqual(regionSelectedNoteIndices(notes, index, 2, 4, 59, 75), [1, 3, 4]);
  assert.deepEqual(regionSelectedNoteIndices(notes, index, 4, 2, 75, 59), [1, 3, 4]);
});

test("indexed rectangle selection agrees with a full scan for unsorted notes and curves", () => {
  const notes = Array.from({ length: 4000 }, (_, i) => ({
    start: ((i * 7919) % 5000) / 100,
    end: ((i * 7919) % 5000) / 100 + (i % 17 + 1) / 10,
    midi: 40 + i % 60,
    kind: i % 7 === 0 ? "curve" as const : "note" as const,
    midi_end: 40 + (i * 3) % 60,
    ctrl1_midi: 30 + i % 80,
    ctrl2_midi: 30 + (i * 5) % 80,
  }));
  const index = buildNoteTimeIndex(notes);
  for (let i = 0; i < 60; i += 1) {
    const t1 = (i * 37 % 490) / 10, t2 = t1 + (i % 8) / 4;
    const p1 = 30 + i % 70, p2 = p1 + (i % 9);
    const expected = notes.flatMap((note, position) => noteIntersects(note, t1, t2, p1, p2) ? [position] : []);
    assert.deepEqual(regionSelectedNoteIndices(notes, index, t1, t2, p1, p2), expected, `rectangle ${i}`);
  }
});

test("dense full-chart rectangle selection keeps index order", () => {
  const notes = Array.from({ length: 4000 }, (_, i) => ({
    start: (i * 37) % 100,
    end: (i * 37) % 100 + 2,
    midi: 60,
  }));
  const selected = regionSelectedNoteIndices(notes, buildNoteTimeIndex(notes), -1, 102, 59, 61);
  assert.equal(selected.length, notes.length);
  assert.equal(selected[0], 0);
  assert.equal(selected.at(-1), notes.length - 1);
});

test("region selection handles a large mostly-offscreen chart", () => {
  const notes = [
    { start: 0, end: 1, midi: 60 },
    { start: 1, end: 2, midi: 60 },
    ...Array.from({ length: 50_000 }, (_, i) => ({ start: 1000 + i, end: 1001 + i, midi: 60 })),
  ];
  const index = buildNoteTimeIndex(notes);
  assert.deepEqual(regionSelectedNoteIndices(notes, index, .5, 1.5, 59, 61), [0, 1]);
});

test("Canvas rectangle selection uses the indexed helper", () => {
  const source = readFileSync(new URL("../src/editor/EditorCanvas.tsx", import.meta.url), "utf8");
  assert.match(source, /cur\.mode==="region"[\s\S]*?regionSelectedNoteIndices\(props\.notes,\s*noteTimeIndex,/);
  assert.doesNotMatch(source, /props\.notes\.flatMap\(\(n,i\)=>noteIntersects\(/);
});

test("wide region avoids allocating a full time-index candidate slice", () => {
  const notes = Array.from({ length: 20_000 }, (_, i) => ({
    start: i / 10, end: i / 10 + .2, midi: i % 2 === 0 ? 60 : 80,
  }));
  const index = buildNoteTimeIndex(notes);
  index.order = new Proxy(index.order, {
    get(target, property, receiver) {
      if (property === "slice") throw new Error("wide region must not copy index candidates");
      return Reflect.get(target, property, receiver);
    },
  });
  // Almost every note overlaps in time, but only half overlap in pitch.
  // The fallback must be selected by time-candidate count, not by pitch hits.
  const selected = regionSelectedNoteIndices(notes, index, -1, 2001, 59, 61);
  assert.deepEqual(selected, Array.from({ length: 10_000 }, (_, i) => i * 2));
});
