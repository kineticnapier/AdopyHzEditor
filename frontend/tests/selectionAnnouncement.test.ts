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
    "2番目のカーブノート、開始2.500秒、E4、選択2件（1番目、2番目）");
});

test("keyboard focus keeps identifying changed members of an equal-size multi-selection", () => {
  const extended = [...notes, { start: 4, end: 4.5, midi: 69 }];
  const before = selectionStatusText(extended, [0, 1, 3], [], 3);
  const after = selectionStatusText(extended, [0, 2, 3], [], 3);
  assert.match(before, /1番目、2番目、4番目/);
  assert.match(after, /1番目、3番目、4番目/);
  assert.notEqual(before, after);
});

test("single keyboard-selected Note still uses the concise detail", () => {
  assert.equal(selectionStatusText(notes, [1], [], 1),
    "2番目のカーブノート、開始2.500秒、E4、選択1件");
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
    "ノートを5件選択中（1番目〜4番目、9番目）");
});

test("changing a hidden middle member of a long Note selection changes the live text", () => {
  const manyNotes = Array.from({ length: 10 }, (_, index) => ({ start: index, end: index + 0.5, midi: 60 }));
  const before = selectionStatusText(manyNotes, [0, 1, 2, 3, 8], [], null);
  const after = selectionStatusText(manyNotes, [0, 1, 2, 4, 8], [], null);
  assert.equal(before, "ノートを5件選択中（1番目〜4番目、9番目）");
  assert.equal(after, "ノートを5件選択中（1番目〜3番目、5番目、9番目）");
  assert.notEqual(before, after);
});

test("keyboard focus does not hide changed middle members in long selections", () => {
  const manyNotes = Array.from({ length: 10 }, (_, index) => ({ start: index, end: index + 0.5, midi: 60 }));
  const before = selectionStatusText(manyNotes, [0, 1, 2, 3, 8], [], 8);
  const after = selectionStatusText(manyNotes, [0, 1, 2, 4, 8], [], 8);
  assert.notEqual(before, after);
  assert.match(after, /1番目〜3番目、5番目、9番目/);
});

test("long Track selections announce middle changes and compress adjacent IDs", () => {
  const before = selectionStatusText(notes, [], [12, 13, 14, 16, 20], null);
  const after = selectionStatusText(notes, [], [12, 13, 14, 17, 20], null);
  assert.equal(before, "Trackを5件選択中（ID 12〜ID 14、ID 16、ID 20）");
  assert.equal(after, "Trackを5件選択中（ID 12〜ID 14、ID 17、ID 20）");
  assert.notEqual(before, after);
});

test("large contiguous selections remain short and do not mutate the selection", () => {
  const manyNotes = Array.from({ length: 1000 }, (_, index) => ({ start: index, end: index + 0.5, midi: 60 }));
  const selected = Array.from({ length: 1000 }, (_, index) => index);
  assert.equal(selectionStatusText(manyNotes, selected, [], null),
    "ノートを1000件選択中（1番目〜1000番目）");
  assert.equal(selected[0], 0);
  assert.equal(selected.at(-1), 999);
});

test("sixteen sparse ranges remain fully identifiable", () => {
  const manyNotes = Array.from({ length: 32 }, (_, index) => ({ start: index, end: index + 0.5, midi: 60 }));
  const selected = Array.from({ length: 16 }, (_, index) => index * 2);
  const before = selectionStatusText(manyNotes, selected, [], null);
  const changed = [...selected];
  changed[8] += 1;
  const after = selectionStatusText(manyNotes, changed, [], null);
  assert.notEqual(before, after);
  assert.match(after, /18番目/);
});

test("very fragmented selections keep aria-live announcements bounded", () => {
  const manyNotes = Array.from({ length: 2000 }, (_, index) => ({ start: index, end: index + 0.5, midi: 60 }));
  const selected = Array.from({ length: 1000 }, (_, index) => index * 2);
  const message = selectionStatusText(manyNotes, selected, [], null);
  assert.equal(message, "ノートを1000件選択中（1番目、3番目、5番目、…、1999番目）");
  assert.ok(message.length < 100);
});

test("clearing selection is announced and stale keyboard focus is ignored", () => {
  assert.equal(selectionStatusText(notes, [], [], null), "選択なし");
  assert.equal(selectionStatusText(notes, [0], [], 1),
    "1番目のノート、開始1.250秒、C4、選択1件");
  assert.equal(selectionStatusText(notes, [999], [], 999), "選択なし");
});

test("Canvas memoizes selection announcements across playback-only renders", () => {
  const source = readFileSync(new URL("../src/editor/EditorCanvas.tsx", import.meta.url), "utf8");
  assert.match(source, /const selectionAnnouncement = useMemo\(\s*\(\) => selectionStatusText\(props\.notes, props\.selected, props\.trackSelection\.ids, keyboardNote\),/);
  assert.match(source, /\[props\.notes, props\.selected, props\.trackSelection\.ids, keyboardNote\],/);
});

test("Canvas renders the memoized selection status in its live region", () => {
  const source = readFileSync(new URL("../src/editor/EditorCanvas.tsx", import.meta.url), "utf8");
  assert.match(source, /aria-live="polite">\{selectionAnnouncement\}<\/span>/);
});
