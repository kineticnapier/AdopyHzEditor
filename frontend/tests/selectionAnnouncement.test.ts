import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { selectionStatusText } from "../src/editor/selectionAnnouncement.ts";
import type { NoteDto } from "../src/editor/bridge.ts";

const notes: NoteDto[] = [
  { start: 1.25, end: 1.5, midi: 60 },
  { start: 2.5, end: 3, midi: 64, kind: "curve" },
  { start: 3.25, end: 3.5, midi: 67 },
];

test("keyboard selection keeps detailed Note announcement", () => {
  assert.equal(selectionStatusText(notes, [0, 1], [], 1),
    "2番目のカーブノート、開始2.500秒、E4、選択2件");
});

test("mouse or Inspector selection identifies the selected Note", () => {
  assert.equal(selectionStatusText(notes, [0], [], null),
    "1番目のノート、開始1.250秒、C4、選択1件");
  assert.equal(selectionStatusText(notes, [1], [], null),
    "2番目のカーブノート、開始2.500秒、E4、選択1件");
});

test("switching Notes without changing the selection count changes the live text", () => {
  const first = selectionStatusText(notes, [0, 1], [], null);
  const second = selectionStatusText(notes, [0, 2], [], null);
  assert.equal(first, "ノートを2件選択中（1番目、2番目）");
  assert.equal(second, "ノートを2件選択中（1番目、3番目）");
  assert.notEqual(first, second);
});

test("Track selection includes IDs so a same-count change is announced", () => {
  const first = selectionStatusText(notes, [], [12, 17], null);
  const second = selectionStatusText(notes, [], [12, 18], null);
  assert.equal(first, "Trackを2件選択中（ID 12、ID 17）");
  assert.equal(second, "Trackを2件選択中（ID 12、ID 18）");
  assert.notEqual(first, second);
});

test("long selections keep the first and last selected items readable", () => {
  const manyNotes = Array.from({ length: 10 }, (_, index) => ({ start: index, end: index + 0.5, midi: 60 }));
  assert.equal(selectionStatusText(manyNotes, [0, 1, 2, 3, 8], [], null),
    "ノートを5件選択中（1番目、2番目、3番目、…、9番目）");
});

test("clearing selection is announced and stale keyboard focus is ignored", () => {
  assert.equal(selectionStatusText(notes, [], [], null), "選択なし");
  assert.equal(selectionStatusText(notes, [0], [], 1),
    "1番目のノート、開始1.250秒、C4、選択1件");
  assert.equal(selectionStatusText(notes, [999], [], 999), "選択なし");
});

test("Canvas uses selectionStatusText in its live region", () => {
  const source = readFileSync(new URL("../src/editor/EditorCanvas.tsx", import.meta.url), "utf8");
  assert.match(source, /aria-live="polite">\{selectionStatusText\(props\.notes, props\.selected, props\.trackSelection\.ids, keyboardNote\)\}<\/span>/);
});
