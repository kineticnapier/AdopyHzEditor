import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { LatestRequestGate } from "../src/api/requestCoordinator.ts";
import test from "node:test";
import { formatCursorPeakLabel } from "../src/editor/cursorStatus.ts";

test("out-of-range cursor hides the fabricated boundary peak", () => {
  const label = formatCursorPeakLabel({
    available: true, peakAvailable: false, time: 0.25,
    cursorMidi: 48.25, cursorName: "C3", cursorCents: 25, cursorHz: 132,
  });
  assert.match(label ?? "", /解析音域外/);
  assert.doesNotMatch(label ?? "", /近傍 C/);
});

test("in-range cursor retains peak details", () => {
  const label = formatCursorPeakLabel({
    available: true, peakAvailable: true, peakName: "C4",
    peakCents: 0, peakHz: 261.63, peakDb: -3,
  });
  assert.match(label ?? "", /近傍 C4/);
  assert.match(label ?? "", /261\.63 Hz/);
});

test("late cursor peak from a replaced document is ignored", async () => {
  const gate = new LatestRequestGate();
  let generation = 0;
  let readout = "new document";
  const request = gate.issue();
  const issuedGeneration = generation;
  let resolve!: (value: string) => void;
  const pending = new Promise<string>((done) => { resolve = done; }).then((value) => {
    if (gate.isCurrent(request) && issuedGeneration === generation)
      readout = value;
  });
  generation += 1;
  gate.invalidate();
  resolve("old document peak");
  await pending;
  assert.equal(readout, "new document");
});

test("moving into a non-CQT view invalidates an earlier peak", async () => {
  const gate = new LatestRequestGate();
  const cqtRequest = gate.issue();
  // cursorMoved issues a ticket even if no new CQT query will be sent.
  gate.issue();
  assert.equal(gate.isCurrent(cqtRequest), false);
});

test("App invalidates CQT cursor diagnostics on every source and document transition", () => {
  const app = readFileSync(new URL("../src/App.tsx", import.meta.url), "utf8");
  assert.match(app, /const peakRequest = useRef\(new LatestRequestGate\(\)\)/);
  const applyState = app.match(/  function applyState\(state: AppState\) \{[\s\S]*?\n  \}/)?.[0];
  assert.ok(applyState);
  assert.match(applyState, /documentGeneration\.current \+= 1;[\s\S]*?peakRequest\.current\.invalidate\(\)/);
  assert.match(applyState, /setCursorReadout\(null\)/);
  const patch = app.match(/  async function patch\(changes: Partial<EditorSettings>\) \{[\s\S]*?\n  \}/)?.[0];
  assert.ok(patch);
  assert.match(patch, /if \(sourceChanged\) \{[\s\S]*?peakRequest\.current\.invalidate\(\)/);
  const transition = app.match(/  async function performStateAction\([\s\S]*?\n  \}/)?.[0];
  assert.ok(transition);
  assert.match(transition, /stateTransitionPending\.current \+= 1;[\s\S]*?peakRequest\.current\.invalidate\(\)/);
  const cursorMoved = app.match(/  async function cursorMoved\(time: number, midi: number\) \{[\s\S]*?\n  \}/)?.[0];
  assert.ok(cursorMoved);
  assert.ok(cursorMoved.indexOf("peakRequest.current.issue()") < cursorMoved.indexOf("if (!api"));
  assert.match(cursorMoved, /peakRequest\.current\.isCurrent\(request\)/);
  assert.match(cursorMoved, /generation !== documentGeneration\.current/);
  assert.match(cursorMoved, /stateTransitionPending\.current > 0/);
});
