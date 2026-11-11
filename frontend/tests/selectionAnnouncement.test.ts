import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { selectionStatusText } from "../src/editor/selectionAnnouncement.ts";
import type { NoteDto } from "../src/editor/bridge.ts";

const notes: NoteDto[] = [
  { start: 1.25, end: 1.5, midi: 60 },
  { start: 2.5, end: 3, midi: 64, kind: "curve" },
];

test("keyboard selection keeps detailed Note announcement", () => {
  assert.equal(selectionStatusText(notes, [0, 1], [], 1),
    "2番目のカーブノート、開始2.500秒、E4、選択2件");
});

test("mouse or Inspector selection without keyboard focus is announced", () => {
  assert.equal(selectionStatusText(notes, [0], [], null), "ノートを1件選択中");
  assert.equal(selectionStatusText(notes, [0, 1], [], null), "ノートを2件選択中");
});

test("Track selection is announced even when keyboard Note focus is absent", () => {
  assert.equal(selectionStatusText(notes, [], [12, 17], null), "Trackを2件選択中");
});

test("clearing selection is announced and stale keyboard focus is ignored", () => {
  assert.equal(selectionStatusText(notes, [], [], null), "選択なし");
  assert.equal(selectionStatusText(notes, [0], [], 1), "ノートを1件選択中");
  assert.equal(selectionStatusText(notes, [999], [], 999), "選択なし");
});

test("Canvas uses selectionStatusText in its live region", () => {
  const source = readFileSync(new URL("../src/editor/EditorCanvas.tsx", import.meta.url), "utf8");
  assert.match(source, /aria-live="polite">\{selectionStatusText\(props\.notes, props\.selected, props\.trackSelection\.ids, keyboardNote\)\}<\/span>/);
});
