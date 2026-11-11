import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { selectionChangeText, selectionStatusText } from "../src/editor/selectionAnnouncement.ts";
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

test("Inspector Track changes are announced even while a Note remains selected", () => {
  const first = selectionStatusText(notes, [0], [12], null);
  const second = selectionStatusText(notes, [0], [13], null);
  assert.equal(first, "1番目のノート、開始1.250秒、C4、選択1件、Trackを1件選択中（ID 12）");
  assert.equal(second, "1番目のノート、開始1.250秒、C4、選択1件、Trackを1件選択中（ID 13）");
  assert.notEqual(first, second);
});

test("keyboard-focused multi-Note selection also reports the selected Tracks", () => {
  assert.equal(selectionStatusText(notes, [0, 1], [12, 13], 1),
    "2番目のカーブノート、開始2.500秒、E4、選択2件（1番目、2番目）、Trackを2件選択中（ID 12、ID 13）");
});

test("multiple mouse-selected Notes do not hide Track selection", () => {
  const text = selectionStatusText(notes, [0, 2], [7], null);
  assert.equal(text, "ノートを2件選択中（1番目、3番目）、Trackを1件選択中（ID 7）");
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

test("17 sparse Note ranges announce a changed hidden middle member", () => {
  const manyNotes = Array.from({ length: 50 }, (_, index) => ({ start: index, end: index + 0.5, midi: 60 }));
  const before = Array.from({ length: 17 }, (_, index) => index * 3);
  const after = [...before];
  after[8] = 25;
  assert.equal(selectionStatusText(manyNotes, before, [], null), selectionStatusText(manyNotes, after, [], null));
  assert.equal(selectionChangeText(before, after, [], [], manyNotes.length),
    "選択変更：ノート追加 26番目、ノート解除 25番目");
});

test("17 sparse Track ranges announce a changed hidden middle ID", () => {
  const before = Array.from({ length: 17 }, (_, index) => 100 + index * 3);
  const after = [...before];
  after[8] = 125;
  assert.equal(selectionStatusText(notes, [], before, null), selectionStatusText(notes, [], after, null));
  assert.equal(selectionChangeText([], [], before, after, notes.length),
    "選択変更：Track追加 ID 125、Track解除 ID 124");
});

test("selection difference ignores invalid Notes and unchanged members", () => {
  assert.equal(selectionChangeText([0, 1], [1, 0], [7], [7], notes.length), "");
  assert.equal(selectionChangeText([0, 999], [0], [], [], notes.length), "");
  assert.equal(selectionChangeText([0], [2], [], [], notes.length),
    "選択変更：ノート追加 3番目、ノート解除 1番目");
});

test("Canvas has a separate live region only for changes hidden by the bounded preview", () => {
  const source = readFileSync(new URL("../src/editor/EditorCanvas.tsx", import.meta.url), "utf8");
  assert.match(source, /const difference = selectionChangeText\(/);
  assert.match(source, /oldStatus === newStatus \? difference : ""/);
  assert.match(source, /id="editor-selection-change"[^>]*aria-live="polite"[^>]*>\{selectionChangeAnnouncement\}<\/span>/);
});


test("duplicate or invalid Track IDs do not inflate spoken selection counts", () => {
  assert.equal(selectionStatusText(notes, [], [12, 12, -1, NaN, Infinity, 13.5], null),
    "Trackを1件選択中（ID 12）");
  assert.equal(selectionStatusText(notes, [], [-1, NaN, Infinity, 1.5], null), "選択なし");
});

test("duplicate Note indices count as one selected Note", () => {
  assert.equal(selectionStatusText(notes, [0, 0, -1, 999, 1.5], [], null),
    "1番目のノート、開始1.250秒、C4、選択1件");
});

test("mixed selection announcement excludes invalid and duplicate Track IDs", () => {
  assert.equal(selectionStatusText(notes, [0], [7, 7, -3, Infinity], null),
    "1番目のノート、開始1.250秒、C4、選択1件、Trackを1件選択中（ID 7）");
});

test("Canvas never compares hidden selection changes across editor generations", () => {
  const source = readFileSync(new URL("../src/editor/EditorCanvas.tsx", import.meta.url), "utf8");
  assert.match(source, /previous && previous\.generation === props\.documentGeneration/);
  assert.match(source, /generation: props\.documentGeneration/);
  assert.match(source, /Different editor states must not report changes between unrelated selections/);
});
