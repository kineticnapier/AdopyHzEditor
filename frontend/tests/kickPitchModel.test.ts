import assert from "node:assert/strict";
import test from "node:test";
import type { KickPitchCandidate, KickPitchPayload } from "../src/api/bridge.ts";
import {
  candidateRoleLabel,
  candidateSummary,
  defaultKickPitchRegion,
  defaultKickPitchSelection,
  kickPitchPolylines,
  validKickPitchRegion,
} from "../src/settings/kickPitchModel.ts";

function candidate(overrides: Partial<KickPitchCandidate> = {}): KickPitchCandidate {
  return {
    id: 0,
    role: "primary",
    harmonicOf: null,
    harmonicNumber: null,
    duration: 0.004,
    medianHz: 100,
    meanConfidence: 0.75,
    times: [0, 0.001, 0.002, 0.003, 0.004],
    hz: [150, 140, 130, 120, 110],
    midi: [50, 49, 48, 47, 46],
    strength: [1, 1, 1, 1, 1],
    confidence: [0.9, 0.9, 0.1, 0.8, 0.8],
    flags: [0, 0, 2, 0, 0],
    ...overrides,
  };
}

function payload(candidates: KickPitchCandidate[], primaryIndex: number | null = 0): KickPitchPayload {
  return {
    available: true,
    status: "",
    start: 0,
    end: 0.004,
    method: "harmonic",
    flagNames: {},
    frames: { times: [], hz: [], midi: [], strength: [], confidence: [], flags: [], windowSeconds: [] },
    candidates,
    primaryIndex,
    stats: {},
  };
}

test("region defaults come from the Track rectangle and fall back to the view", () => {
  const fromRange = defaultKickPitchRegion({ startTime: 1, endTime: 1.4, minMidi: 33, maxMidi: 69 }, 0);
  assert.equal(fromRange.start, 1);
  assert.equal(fromRange.end, 1.4);
  assert.equal(fromRange.minHz, 55);
  assert.equal(fromRange.maxHz, 440);
  assert.deepEqual(defaultKickPitchRegion(null, 2), { start: 2, end: 2.5, minHz: 25, maxHz: 500 });
});

test("region validation rejects empty, too long and inverted ranges", () => {
  assert.equal(validKickPitchRegion({ start: 0, end: 0.5, minHz: 25, maxHz: 500 }), null);
  assert.ok(validKickPitchRegion({ start: 0, end: 0.005, minHz: 25, maxHz: 500 }));
  assert.ok(validKickPitchRegion({ start: 0, end: 11, minHz: 25, maxHz: 500 }));
  assert.ok(validKickPitchRegion({ start: 0, end: 1, minHz: 100, maxHz: 120 }));
  assert.ok(validKickPitchRegion({ start: 0, end: Number.NaN, minHz: 25, maxHz: 500 }));
});

test("labels describe the role and the sweep", () => {
  assert.equal(candidateRoleLabel(candidate()), "主（基本周波数）");
  assert.equal(candidateRoleLabel(candidate({ role: "harmonic", harmonicNumber: 12 })), "倍音 ×12");
  assert.equal(candidateRoleLabel(candidate({ role: "independent" })), "独立成分");
  assert.equal(candidateSummary(candidate()), "150.0→110.0 Hz · 0.004 s · 信頼度 75%");
});

test("only the primary candidate is preselected", () => {
  const p = payload([candidate({ id: 3, role: "independent" }), candidate({ id: 7 })], 1);
  assert.deepEqual(defaultKickPitchSelection(p), [7]);
  assert.deepEqual(defaultKickPitchSelection(payload([], null)), []);
  assert.deepEqual(defaultKickPitchSelection(null), []);
});

test("low-confidence points split polylines instead of being bridged", () => {
  const lines = kickPitchPolylines(payload([candidate()]), 0.5);
  assert.equal(lines.length, 2);
  assert.deepEqual(lines[0].points.map((p) => p.midi), [50, 49]);
  assert.deepEqual(lines[1].points.map((p) => p.midi), [47, 46]);
  assert.equal(kickPitchPolylines(payload([candidate()]), 0.05)[0].points.length, 5);
});
