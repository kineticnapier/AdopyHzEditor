import assert from "node:assert/strict";
import test from "node:test";
import { dispatchEditorShortcut, type ShortcutActions, type ShortcutEvent } from "../src/editor/shortcutDispatch.ts";

type Modifiers = Partial<Pick<ShortcutEvent, "ctrlKey" | "metaKey" | "altKey" | "shiftKey">>;

function setup() {
  const calls: string[] = [];
  const log = (name: string) => () => { calls.push(name); };
  const a: ShortcutActions = {
    notes: [], selected: [0], playbackTime: 37,
    view: { mode: "spec", start: 0, windowSeconds: 12, pitchBottom: 24, visibleNotes: 60 },
    nudgeSeconds: .25,
    openAudio: log("open"), saveProject: log("save"), saveProjectAs: log("saveAs"),
    loadProject: log("load"), importMidi: log("import"), exportMidi: log("export"),
    openAdoExport: log("adoExport"), openHelp: log("help"), setStatus: () => {},
    undo: log("undo"), redo: log("redo"), duplicate: log("duplicate"),
    quantize: log("quantize"), select: indices => calls.push("select:" + indices.join(",")),
    copy: log("copy"), cut: log("cut"), paste: log("paste"), applyTargetAngle: log("angle"),
    move: (_indices, dx, dy) => calls.push(`move:${dx},${dy}`),
    stop: log("stop"), play: log("play"), deleteSelected: log("delete"),
    mode: mode => calls.push("mode:" + mode),
    seek: delta => calls.push("seek:" + delta),
    seekTo: time => calls.push("seekTo:" + time),
    updateView: changes => calls.push("view:" + JSON.stringify(changes)),
  };
  const press = (key: string, mods: Modifiers = {}) => {
    let prevented = false;
    dispatchEditorShortcut({
      key, ctrlKey: false, metaKey: false, altKey: false, shiftKey: false,
      preventDefault() { prevented = true; }, ...mods,
    }, a);
    return prevented;
  };
  return { calls, press };
}

test("Ctrl/Meta/Alt with plain editor keys never changes pitch or mode", () => {
  const { calls, press } = setup();
  for (const [key, mods] of [
    ["w", { ctrlKey: true }], ["w", { metaKey: true }], ["w", { altKey: true }],
    ["1", { ctrlKey: true }], ["2", { altKey: true }], ["3", { metaKey: true }],
    ["Delete", { ctrlKey: true }], ["ArrowLeft", { ctrlKey: true }],
    ["ArrowUp", { ctrlKey: true, altKey: true }],
  ] as const) assert.equal(press(key, mods), false, key);
  assert.deepEqual(calls, []);
});

test("unmodified editor keys keep their existing actions", () => {
  const { calls, press } = setup();
  for (const key of ["1", "2", "3", "w", "s", "ArrowLeft", "Delete"]) assert.equal(press(key), true, key);
  assert.deepEqual(calls, [
    "mode:spec", "mode:notes", "mode:both", 'view:{"pitchBottom":36}',
    'view:{"pitchBottom":12}', "seek:-1", "delete",
  ]);
});

test("Home seeks to exactly zero and modified Home remains native", () => {
  const { calls, press } = setup();
  assert.equal(press("Home"), true);
  assert.equal(press("Home", { ctrlKey: true }), false);
  assert.deepEqual(calls, ["seekTo:0"]);
});

test("assigned Ctrl and Shift combinations still work", () => {
  const { calls, press } = setup();
  assert.equal(press("s", { ctrlKey: true }), true);
  assert.equal(press("s", { ctrlKey: true, shiftKey: true }), true);
  assert.equal(press("ArrowUp", { ctrlKey: true }), true);
  assert.equal(press("ArrowLeft", { ctrlKey: true, shiftKey: true }), true);
  assert.equal(press(" ", { ctrlKey: true }), true);
  assert.equal(press(" ", {}), true);
  assert.equal(press("ArrowRight", { shiftKey: true }), true);
  assert.deepEqual(calls, ["save", "saveAs", 'view:{"pitchBottom":36}', "move:-0.25,0", "stop", "play", "seek:5"]);
});
