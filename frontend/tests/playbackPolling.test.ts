import assert from "node:assert/strict";
import test from "node:test";
import { readFileSync } from "node:fs";
import { createSingleFlightPoll, LatestRequestGate } from "../src/api/requestCoordinator.ts";

test("slow playback polling never invalidates its own pending response", async () => {
  const gate = new LatestRequestGate();
  const applied: number[] = [];
  let resolve!: (value: number) => void;
  let calls = 0;
  const poll = createSingleFlightPoll(async () => {
    calls += 1;
    const request = gate.issue();
    const value = await new Promise<number>(done => { resolve = done; });
    if (gate.isCurrent(request)) applied.push(value);
  });
  const first = poll();
  await poll();
  await poll();
  assert.equal(calls, 1);
  resolve(42);
  await first;
  assert.deepEqual(applied, [42]);
  const next = poll();
  assert.equal(calls, 2);
  resolve(43);
  await next;
  assert.deepEqual(applied, [42, 43]);
});

test("failed playback polling releases the single-flight guard", async () => {
  let calls = 0;
  const poll = createSingleFlightPoll(async () => {
    calls += 1;
    if (calls === 1) throw new Error("temporary backend failure");
  });
  await poll();
  await poll();
  assert.equal(calls, 2);
});

test("a document switch can still invalidate an in-flight playback response", async () => {
  const gate = new LatestRequestGate();
  let release!: (value: number) => void;
  let applied: number | null = null;
  const poll = createSingleFlightPoll(async () => {
    const request = gate.issue();
    const value = await new Promise<number>(done => { release = done; });
    if (gate.isCurrent(request)) applied = value;
  });
  const inFlight = poll();
  gate.invalidate();
  release(10);
  await inFlight;
  assert.equal(applied, null);
});

test("App playback timer uses single-flight polling with generation guards", () => {
  const source = readFileSync(new URL("../src/App.tsx", import.meta.url), "utf8");
  assert.match(source, /const pollPlayback = createSingleFlightPoll\(async \(\) => \{/);
  assert.match(source, /const request = playbackRequests\.current\.issue\(\)/);
  assert.match(source, /generation === documentGeneration\.current/);
  assert.match(source, /playbackRequests\.current\.isCurrent\(request\)/);
  assert.match(source, /void pollPlayback\(\)/);
});
