import assert from "node:assert/strict";
import test from "node:test";
import { runMidiExport } from "../src/editor/midiExport.ts";

test("MIDI export reports success and cancellation statuses", async () => {
  const statuses: string[] = [];
  await runMidiExport(async () => ({ status: "notes.mid をMIDI出力しました" }), value => statuses.push(value));
  await runMidiExport(async () => ({ status: "キャンセルしました" }), value => statuses.push(value));
  assert.deepEqual(statuses, ["notes.mid をMIDI出力しました", "キャンセルしました"]);
});

test("MIDI export reports rejected writes", async () => {
  let status = "";
  await runMidiExport(
    async () => { throw new Error("Permission denied"); },
    value => { status = value; },
  );
  assert.match(status, /MIDI出力に失敗しました/);
  assert.match(status, /Permission denied/);
});
