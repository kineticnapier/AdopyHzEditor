import assert from "node:assert/strict";
import test from "node:test";
import { midiLabel, midiToHz } from "../src/editor/musicMath.ts";

test("MIDI labels remain correct at editor boundaries",()=>{
  assert.equal(midiLabel(0),"C-1");
  assert.equal(midiLabel(69),"A4");
  assert.equal(midiLabel(127),"G9");
});

test("fractional MIDI readouts retain continuous Hz while using the nearest note label",()=>{
  assert.equal(midiLabel(69.49),"A4");
  assert.equal(midiLabel(69.51),"A#4");
  assert.ok(Math.abs(midiToHz(69.5)-452.8929841231365)<1e-9);
});
