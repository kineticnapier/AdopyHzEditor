import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { dispatchEditorShortcut, type ShortcutActions, type ShortcutEvent } from "../src/editor/shortcutDispatch.ts";

type Modifiers = Partial<Pick<ShortcutEvent, "ctrlKey" | "metaKey" | "altKey" | "shiftKey" | "repeat" | "getModifierState">>;

function setup(viewOverrides: Partial<ShortcutActions["view"]> = {}) {
  const calls: string[] = [];
  const log = (name: string) => () => { calls.push(name); };
  const a: ShortcutActions = {
    notes: [], selected: [0], playbackTime: 37,
    view: { mode: "spec", start: 0, windowSeconds: 12, pitchBottom: 24, visibleNotes: 60, ...viewOverrides },
    nudgeSeconds: .25,
    openAudio: log("open"), saveProject: log("save"), saveProjectAs: log("saveAs"),
    loadProject: log("load"), importMidi: log("import"), exportMidi: log("export"),
    openAdoExport: log("adoExport"), openHelp: log("help"), setStatus: () => {},
    undo: log("undo"), redo: log("redo"), duplicate: log("duplicate"),
    quantize: log("quantize"), select: indices => calls.push("select:" + indices.join(",")),
    clearTracks: log("clearTracks"),
    copy: log("copy"), cut: log("cut"), paste: log("paste"), applyTargetAngle: log("angle"),
    move: (_indices, dx, dy) => calls.push(`move:${dx},${dy}`),
    stop: log("stop"), play: log("play"), deleteSelected: log("delete"),
    mode: mode => calls.push("mode:" + mode),
    seek: delta => calls.push("seek:" + delta),
    seekTo: time => calls.push("seekTo:" + time),
    updateView: changes => calls.push("view:" + JSON.stringify(changes)),
  };
  const press = (key: string, mods: Modifiers = {}, target?: EventTarget | null) => {
    let prevented = false;
    dispatchEditorShortcut({
      key, ctrlKey: false, metaKey: false, altKey: false, shiftKey: false,
      target, preventDefault() { prevented = true; }, ...mods,
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

test("Shift+Delete, Shift+Backspace and Shift+Q never mutate notes", () => {
  const { calls, press } = setup();
  for (const key of ["Delete", "Backspace", "q"]) {
    assert.equal(press(key, { shiftKey: true }), false, `Shift+${key}`);
  }
  assert.deepEqual(calls, []);
  assert.equal(press("Delete"), true);
  assert.equal(press("Backspace"), true);
  assert.equal(press("q"), true);
  // Shift+arrow navigation is intentionally assigned and must still work.
  assert.equal(press("ArrowRight", { shiftKey: true }), true);
  assert.deepEqual(calls, ["delete", "delete", "quantize", "seek:5"]);
});

test("unassigned Shift+Home and Shift+W/S do not seek or scroll pitch", () => {
  const { calls, press } = setup();
  for (const key of ["Home", "w", "s", "W", "S"]) {
    assert.equal(press(key, { shiftKey: true }), false, `Shift+${key}`);
  }
  assert.deepEqual(calls, []);
  assert.equal(press("Home"), true);
  assert.equal(press("w"), true);
  assert.equal(press("s"), true);
  assert.deepEqual(calls, ["seekTo:0", 'view:{"pitchBottom":36}', 'view:{"pitchBottom":12}']);
});

test("unassigned Shift+Space, vertical arrows and mode keys preserve native behavior", () => {
  const { calls, press } = setup();
  for (const key of [" ", "ArrowUp", "ArrowDown", "1", "2", "3"]) {
    assert.equal(press(key, { shiftKey: true }), false, `Shift+${key}`);
  }
  assert.deepEqual(calls, []);
  for (const key of [" ", "ArrowUp", "ArrowDown", "1", "2", "3"]) {
    assert.equal(press(key), true, key);
  }
  assert.equal(press("ArrowUp", { ctrlKey: true }), true);
  assert.equal(press("ArrowDown", { ctrlKey: true }), true);
  assert.equal(press("ArrowRight", { shiftKey: true }), true);
  assert.equal(press("ArrowLeft", { shiftKey: true }), true);
  assert.deepEqual(calls, [
    "play", 'view:{"pitchBottom":25}', 'view:{"pitchBottom":23}',
    "mode:spec", "mode:notes", "mode:both",
    'view:{"pitchBottom":36}', 'view:{"pitchBottom":12}', "seek:5", "seek:-5",
  ]);
});

test("F1 opens help only without modifiers and does not consume native chords", () => {
  const { calls, press } = setup();
  assert.equal(press("F1"), true);
  for (const mods of [
    { ctrlKey: true }, { metaKey: true }, { altKey: true }, { shiftKey: true },
    { ctrlKey: true, shiftKey: true }, { altKey: true, shiftKey: true },
  ]) {
    assert.equal(press("F1", mods), false);
    assert.equal(press("F1", { ...mods, repeat: true }), false);
  }
  assert.equal(press("F1", { repeat: true }), true);
  assert.deepEqual(calls, ["help"]);
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


test("Ctrl+S commits the focused number input before invoking save", () => {
  const { calls, press } = setup();
  const input = {
    closest(selector: string) {
      assert.match(selector, /input/);
      return { blur() { calls.push("commit-input"); } };
    },
  } as unknown as EventTarget;
  assert.equal(press("s", { ctrlKey: true }, input), true);
  assert.deepEqual(calls, ["commit-input", "save"]);
});

test("Ctrl+Shift+S and Meta+S commit focused edits before saving", () => {
  const { calls, press } = setup();
  const field = {
    closest() { return { blur() { calls.push("commit-input"); } }; },
  } as unknown as EventTarget;
  assert.equal(press("s", { ctrlKey: true, shiftKey: true }, field), true);
  assert.equal(press("s", { metaKey: true }, field), true);
  assert.deepEqual(calls, ["commit-input", "saveAs", "commit-input", "save"]);
});

test("held file shortcuts are consumed without repeating save or dialogs", () => {
  const { calls, press } = setup();
  const input = {
    closest: () => ({ blur: () => calls.push("blur") }),
  } as unknown as EventTarget;
  for (const [key, mods] of [
    ["s", { ctrlKey: true, repeat: true }],
    ["s", { ctrlKey: true, shiftKey: true, repeat: true }],
    ["s", { metaKey: true, repeat: true }],
    ["o", { ctrlKey: true, repeat: true }],
    ["l", { ctrlKey: true, repeat: true }],
    ["i", { ctrlKey: true, repeat: true }],
    ["m", { ctrlKey: true, repeat: true }],
    ["e", { ctrlKey: true, repeat: true }],
    ["F1", { repeat: true }],
  ] as const) assert.equal(press(key, mods, input), true, key);
  assert.deepEqual(calls, []);
  assert.equal(press("s", { ctrlKey: true }, input), true);
  assert.deepEqual(calls, ["blur", "save"]);
});

test("key repeats still support navigation and undo without hijacking unassigned chords", () => {
  const { calls, press } = setup();
  assert.equal(press("ArrowRight", { repeat: true }), true);
  assert.equal(press("ArrowUp", { ctrlKey: true, repeat: true }), true);
  assert.equal(press("z", { ctrlKey: true, repeat: true }), true);
  assert.equal(press("o", { ctrlKey: true, shiftKey: true, repeat: true }), false);
  assert.deepEqual(calls, ["seek:1", 'view:{"pitchBottom":36}', "undo"]);
});

test("save shortcuts do not blur non-editing targets or fail without a target", () => {
  const { calls, press } = setup();
  const button = {
    closest() { return null; },
  } as unknown as EventTarget;
  assert.equal(press("s", { ctrlKey: true }, button), true);
  assert.equal(press("s", { ctrlKey: true, shiftKey: true }), true);
  assert.deepEqual(calls, ["save", "saveAs"]);
});


test("Document-like keydown targets can save without a closest method", () => {
  const { calls, press } = setup();
  const targets = [null, {}, { nodeType: 9 }, { nodeType: 3 }];
  for (const target of targets) {
    assert.equal(press("s", { ctrlKey: true }, target as EventTarget | null), true);
    assert.equal(press("s", { ctrlKey: true, shiftKey: true }, target as EventTarget | null), true);
  }
  assert.deepEqual(calls, targets.flatMap(() => ["save", "saveAs"]));
});

test("non-callable closest on a keydown target never blocks Meta+S", () => {
  const { calls, press } = setup();
  const targets = [{ closest: undefined }, { closest: null }, { closest: 5 }];
  for (const target of targets) {
    assert.equal(press("s", { metaKey: true }, target as unknown as EventTarget), true);
  }
  assert.deepEqual(calls, ["save", "save", "save"]);
});

test("AltGraph and unassigned Ctrl+Alt chords do not trigger editor actions", () => {
  const { calls, press } = setup();
  const input = {
    closest: () => ({ blur: () => calls.push("blur") }),
  } as unknown as EventTarget;
  assert.equal(press("s", { ctrlKey: true, altKey: true }, input), false);
  assert.equal(press("s", { ctrlKey: true, altKey: true, shiftKey: true }, input), false);
  assert.equal(press("o", { ctrlKey: true, altKey: true }), false);
  const altGraph = { ctrlKey: true, altKey: true, getModifierState: (name: string) => name === "AltGraph" };
  assert.equal(press("s", altGraph, input), false);
  assert.equal(press("a", altGraph), false);
  assert.deepEqual(calls, []);
  assert.equal(press("a", { ctrlKey: true, altKey: true }), true);
  assert.deepEqual(calls, ["angle"]);
});

test("unassigned Ctrl+Shift and Meta+Shift chords do not run editor actions", () => {
  const { calls, press } = setup();
  for (const key of ["i", "m", "e", "o", "l", "a", "c", "x", "v", "d", "y", " "]) {
    assert.equal(press(key, { ctrlKey: true, shiftKey: true }), false, `Ctrl+Shift+${key}`);
    assert.equal(press(key, { metaKey: true, shiftKey: true }), false, `Meta+Shift+${key}`);
  }
  assert.equal(press("a", { ctrlKey: true, altKey: true, shiftKey: true }), false);
  assert.deepEqual(calls, []);
});

test("explicit Ctrl+Shift actions and Ctrl+Alt+A still work", () => {
  const { calls, press } = setup();
  assert.equal(press("s", { ctrlKey: true, shiftKey: true }), true);
  assert.equal(press("z", { ctrlKey: true, shiftKey: true }), true);
  assert.equal(press("ArrowLeft", { ctrlKey: true, shiftKey: true }), true);
  assert.equal(press("ArrowRight", { ctrlKey: true, shiftKey: true }), true);
  assert.equal(press("ArrowUp", { ctrlKey: true, shiftKey: true }), true);
  assert.equal(press("ArrowDown", { ctrlKey: true, shiftKey: true }), true);
  assert.equal(press("a", { ctrlKey: true, altKey: true }), true);
  assert.deepEqual(calls, [
    "saveAs", "redo", "move:-0.25,0", "move:0.25,0",
    "move:0,1", "move:0,-1", "angle",
  ]);
});

test("keyboard pitch scrolling never moves the view outside MIDI 0..127", () => {
  const upper = setup({ pitchBottom: 65, visibleNotes: 60 });
  assert.equal(upper.press("w"), true);
  assert.equal(upper.press("ArrowUp"), true);
  assert.equal(upper.press("ArrowUp", { ctrlKey: true }), true);
  assert.deepEqual(upper.calls, [
    'view:{"pitchBottom":68}',
    'view:{"pitchBottom":66}',
    'view:{"pitchBottom":68}',
  ]);
  const lower = setup({ pitchBottom: 0, visibleNotes: 128 });
  assert.equal(lower.press("s"), true);
  assert.equal(lower.press("ArrowDown"), true);
  assert.deepEqual(lower.calls, []);
});

test("keyboard pitch keys at MIDI boundaries do not request unchanged views", () => {
  const upper = setup({ pitchBottom: 68, visibleNotes: 60 });
  for (const [key, mods] of [
    ["w", {}], ["ArrowUp", {}], ["ArrowUp", { ctrlKey: true }],
  ] as const) assert.equal(upper.press(key, mods), true);
  assert.deepEqual(upper.calls, []);
  assert.equal(upper.press("s"), true);
  assert.deepEqual(upper.calls, ['view:{"pitchBottom":56}']);

  const lower = setup({ pitchBottom: 0, visibleNotes: 60 });
  for (const [key, mods] of [
    ["s", {}], ["ArrowDown", {}], ["ArrowDown", { ctrlKey: true }],
  ] as const) assert.equal(lower.press(key, mods), true);
  assert.deepEqual(lower.calls, []);
  assert.equal(lower.press("w"), true);
  assert.deepEqual(lower.calls, ['view:{"pitchBottom":12}']);

  const full = setup({ pitchBottom: 0, visibleNotes: 128 });
  assert.equal(full.press("w"), true);
  assert.equal(full.press("s"), true);
  assert.deepEqual(full.calls, []);
});

test("global Escape clears Frequency Tracks before Notes", () => {
  const { calls, press } = setup();
  assert.equal(press("Escape"), true);
  assert.deepEqual(calls, ["clearTracks", "select:"]);
});

test("modified Escape does not clear either selection", () => {
  const { calls, press } = setup();
  assert.equal(press("Escape", { ctrlKey: true }), false);
  assert.equal(press("Escape", { altKey: true }), false);
  assert.equal(press("Escape", { metaKey: true }), false);
  assert.equal(press("Escape", { shiftKey: true }), false);
  assert.deepEqual(calls, []);
});

test("global Track clearing is wired through the request-invalidating App handler", () => {
  const source = readFileSync(new URL("../src/App.tsx", import.meta.url), "utf8");
  assert.match(source, /clearTracks:\s*\(\)\s*=>\s*changeTrackSelection\(\{\s*ids:\s*\[\],\s*range:\s*null,\s*useRange:\s*false\s*\}\)/);
  assert.match(source, /function changeTrackSelection\([\s\S]*?trackSelectionRequests\.current\.invalidate\(\)/);
});


test("save commits all supported contenteditable variants before invoking save", () => {
  for (const [value, modifiers, expected] of [
    ["", { ctrlKey: true }, "save"],
    ["plaintext-only", { metaKey: true }, "save"],
    ["true", { ctrlKey: true, shiftKey: true }, "saveAs"],
  ] as const) {
    const { calls, press } = setup();
    const editable = { blur() { calls.push("commit-editable"); } };
    const target = {
      closest(selector: string) {
        return selector.split(",").includes(`[contenteditable='${value}']`) ? editable : null;
      },
    } as unknown as EventTarget;
    assert.equal(press("s", modifiers, target), true, value);
    assert.deepEqual(calls, ["commit-editable", expected], value);
  }
});

test("held Space and Ctrl/Meta+Space never repeat transport requests", () => {
  const { calls, press } = setup();
  for (const mods of [{}, { ctrlKey: true }, { metaKey: true }]) {
    assert.equal(press(" ", { ...mods, repeat: true }), true);
    assert.equal(press(" ", mods), true);
    assert.equal(press(" ", { ...mods, repeat: true }), true);
  }
  assert.deepEqual(calls, ["play", "stop", "stop"]);
  // Unassigned modified Space chords retain native behavior.
  for (const mods of [{ shiftKey: true }, { altKey: true }, { ctrlKey: true, shiftKey: true }]) {
    assert.equal(press(" ", { ...mods, repeat: true }), false);
  }
});
