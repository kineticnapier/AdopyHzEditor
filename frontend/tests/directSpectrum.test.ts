import assert from "node:assert/strict";
import test from "node:test";
import {
  DirectSpectrumRegionCache,
  FOLLOW_TARGET_RATIO,
  FOLLOW_TRIGGER_RATIO,
  followViewportStart,
  spectrumLayersForMode,
  spectrumRegionKey,
  type SpectrumRegion,
} from "../src/editor/directSpectrum.ts";

const baseRegion: SpectrumRegion = {
  startTime: 0, endTime: 10, minMidi: 20, maxMidi: 80,
  pixelWidth: 800, pixelHeight: 500, threshold: 2,
};

test("cursor movement inside the dead-zone keeps the viewport fixed", () => {
  assert.equal(followViewportStart(10, 10, 10 + 10 * (FOLLOW_TRIGGER_RATIO - 0.01), 100), null);
});

test("Raw, Tracks, and Both select the intended spectrum sub-layers", () => {
  assert.deepEqual(spectrumLayersForMode("raw"), { raw: true, tracks: false });
  assert.deepEqual(spectrumLayersForMode("tracks"), { raw: false, tracks: true });
  assert.deepEqual(spectrumLayersForMode("both"), { raw: true, tracks: true });
});

test("crossing the follow threshold advances one prefetched page", () => {
  const next = followViewportStart(10, 10, 10 + 10 * (FOLLOW_TRIGGER_RATIO + 0.01), 100);
  assert.ok(next !== null);
  assert.ok(Math.abs((10 + 10 * (FOLLOW_TRIGGER_RATIO - FOLLOW_TARGET_RATIO)) - next) < 1e-9);
});

test("same region is cached and concurrent requests are deduplicated", async () => {
  let resolve!: (value: { available: boolean }) => void;
  let calls = 0;
  const cache = new DirectSpectrumRegionCache(() => {
    calls += 1;
    return new Promise(done => { resolve = done; });
  });
  const first = cache.load(baseRegion);
  const duplicate = cache.load({ ...baseRegion });
  assert.equal(calls, 1);
  resolve({ available: true });
  assert.deepEqual(await first, { available: true });
  assert.deepEqual(await duplicate, { available: true });
  assert.deepEqual(await cache.load(baseRegion), { available: true });
  assert.equal(calls, 1);
  assert.equal(cache.stats.backendQueries, 1);
});

test("one second of cursor-only animation does not repeat raw or track queries", async () => {
  let rawCalls = 0, trackCalls = 0;
  const rawCache = new DirectSpectrumRegionCache(async () => { rawCalls += 1; return { available: true }; });
  const trackCache = new DirectSpectrumRegionCache(async () => { trackCalls += 1; return { available: true, pointCount: 1 }; });
  await rawCache.load(baseRegion);
  await trackCache.load(baseRegion);
  for (let frame = 0; frame < 60; frame += 1) {
    const cursorTime = 1 + frame / 60;
    assert.equal(followViewportStart(0, 10, cursorTime, 100), null);
  }
  assert.equal(rawCalls, 1);
  assert.equal(trackCalls, 1);
  assert.equal(rawCache.stats.backendQueries, 1);
  assert.equal(trackCache.stats.backendQueries, 1);
});

test("an invalidated stale request cannot repopulate or rewind the viewport", async () => {
  const resolvers: Array<(value: { available: boolean; startTime: number }) => void> = [];
  const cache = new DirectSpectrumRegionCache(() => new Promise(done => { resolvers.push(done); }));
  const stale = cache.load(baseRegion);
  cache.invalidate();
  const currentRegion = { ...baseRegion, startTime: 40, endTime: 50 };
  const current = cache.load(currentRegion);
  resolvers[1]({ available: true, startTime: 40 });
  assert.equal((await current)?.startTime, 40);
  resolvers[0]({ available: true, startTime: 0 });
  assert.equal(await stale, null);
  assert.equal(cache.stats.staleResults, 1);
});

test("a stale track viewport response is ignored after a manual region change", async () => {
  type TrackPayload = { available: boolean; startTime: number; pointCount: number };
  const resolvers: Array<(value: TrackPayload) => void> = [];
  const cache = new DirectSpectrumRegionCache<TrackPayload>(() => new Promise(done => { resolvers.push(done); }));
  const oldViewport = cache.load(baseRegion);
  cache.invalidate();
  const movedRegion = { ...baseRegion, startTime: 20, endTime: 30 };
  const movedViewport = cache.load(movedRegion);
  resolvers[1]({ available: true, startTime: 20, pointCount: 200 });
  assert.equal((await movedViewport)?.startTime, 20);
  resolvers[0]({ available: true, startTime: 0, pointCount: 300 });
  assert.equal(await oldViewport, null);
});

test("a manual seek outside the viewport selects the target-zone region", () => {
  const start = followViewportStart(0, 10, 55, 100);
  assert.equal(start, 55 - 10 * FOLLOW_TARGET_RATIO);
  assert.notEqual(spectrumRegionKey(baseRegion), spectrumRegionKey({ ...baseRegion, startTime: start!, endTime: start! + 10 }));
});
