import assert from "node:assert/strict";
import test from "node:test";
import { dispatchEditorShortcut, type ShortcutActions, type ShortcutEvent } from "../src/editor/shortcutDispatch.ts";

type Mods = Partial<Pick<ShortcutEvent, "ctrlKey" | "metaKey" | "altKey" | "shiftKey" | "getModifierState">>;

function fixture() {
  const calls: string[] = [];
  const values = {
    notes: [], selected: [0], playbackTime: 1, nudgeSeconds: 0.25,
    view: { mode: "spec", start: 0, windowSeconds: 10, pitchBottom: 20, visibleNotes: 60 },
  };
  const actions = new Proxy(values, {
    get(target, property) {
      if (property in target) return Reflect.get(target, property);
      return () => { calls.push(String(property)); };
    },
  }) as ShortcutActions;
  function press(key: string, mods: Mods = {}, repeat = false): boolean {
    let prevented = false;
    dispatchEditorShortcut({
      key, ctrlKey: false, metaKey: false, altKey: false, shiftKey: false,
      ...mods, repeat, preventDefault() { prevented = true; },
    }, actions);
    return prevented;
  }
  return { calls, press };
}

test("selection-changing shortcuts consume auto-repeat but accept fresh keydowns", () => {
  const cases: Array<[string, Mods, string]> = [
    ["x", { ctrlKey: true }, "cut"],
    ["X", { metaKey: true }, "cut"],
    ["v", { ctrlKey: true }, "paste"],
    ["d", { metaKey: true }, "duplicate"],
    ["a", { ctrlKey: true, altKey: true }, "applyTargetAngle"],
    ["q", {}, "quantize"],
    ["Delete", {}, "deleteSelected"],
    ["Backspace", {}, "deleteSelected"],
  ];
  for (const [key, mods, action] of cases) {
    const { calls, press } = fixture();
    assert.equal(press(key, mods), true, key);
    assert.equal(press(key, mods, true), true, key + " repeat");
    assert.deepEqual(calls, [action], key);
    assert.equal(press(key, mods), true, key + " fresh press");
    assert.deepEqual(calls, [action, action], key);
  }
});

test("held navigation and Undo remain repeatable", () => {
  const { calls, press } = fixture();
  assert.equal(press("z", { ctrlKey: true }, true), true);
  assert.equal(press("z", { ctrlKey: true }, true), true);
  assert.equal(press("ArrowRight", {}, true), true);
  assert.equal(press("ArrowRight", {}, true), true);
  assert.deepEqual(calls, ["undo", "undo", "seek", "seek"]);
});

test("unassigned or text-entry chords remain untouched on repeat", () => {
  const { calls, press } = fixture();
  assert.equal(press("x", { ctrlKey: true, shiftKey: true }, true), false);
  assert.equal(press("q", { shiftKey: true }, true), false);
  assert.equal(press("Delete", { shiftKey: true }, true), false);
  assert.equal(press("a", {
    ctrlKey: true, altKey: true,
    getModifierState: (name) => name === "AltGraph",
  }, true), false);
  assert.deepEqual(calls, []);
});
