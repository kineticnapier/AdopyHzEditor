import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const dialogSource = readFileSync(
  new URL("../src/dialogs/AdoFAIExportDialogJa.tsx", import.meta.url),
  "utf8",
).replace(/\r\n/g, "\n");
const backendSource = readFileSync(new URL("../../web/adofai.py", import.meta.url), "utf8");

test("Harmony export shows the output BPM it actually uses", () => {
  // Harmony timing runs at angle_only_bpm; hiding the field left it stuck at
  // the project BPM x 10 default.
  const start = dialogSource.indexOf('<Field label="出力BPM">');
  assert.ok(start > 0, "output BPM field exists");
  const guard = dialogSource.slice(dialogSource.lastIndexOf("{", start), start);
  assert.match(guard, /isAngle \|\| isHarmony/);
  assert.match(dialogSource, /value=\{options\.angleOnlyBpm\}/);
});

test("Angle Compression no longer asks for a base BPM", () => {
  // Tile counts are freq x duration there, so the base BPM cancels out.
  assert.doesNotMatch(dialogSource, /基準BPM/);
  assert.doesNotMatch(dialogSource, /options\.baseBpm/);
  assert.doesNotMatch(backendSource, /raw\.get\("baseBpm"\)/);
});

test("ratio-polyrhythm picks its cycle length from pitch, beat or output BPM", () => {
  assert.match(dialogSource, /\["pitch", "音の高さ（Hz）"\]/);
  assert.match(dialogSource, /cycleTiming = options\.harmonyPolyCycleTiming \?\? "pitch"/);
  assert.match(dialogSource, /patch\("harmonyPolyBeatsPerCycle", v\)/);
  // The manual output BPM input only shows for manual timing in ratio mode.
  assert.match(dialogSource, /!\(isHarmony && isRatioPoly && cycleTiming !== "manual"\)/);
  assert.match(backendSource, /def beat_synced_output_bpm/);
  assert.match(backendSource, /"harmonyPolyCycleTiming": "pitch"/);
});

test("beat-synced output BPM matches the backend formula", async () => {
  const { beatSyncedOutputBpm } = await import("../src/dialogs/beatSync.ts");
  // 190 BPM song, 720 degree cycle, one beat per cycle -> 760.
  assert.equal(beatSyncedOutputBpm(190, 720, 1), 760);
  assert.equal(beatSyncedOutputBpm(190, 720, 0.5), 1520);
  assert.ok(Number.isNaN(beatSyncedOutputBpm(0, 720, 1)));
});

test("overlap chords expose legato and octave cleanup", () => {
  assert.match(dialogSource, /patch\("harmonyPolyLegatoMs", v\)/);
  assert.match(dialogSource, /patch\("harmonyPolyMergeOctaves", e\.target\.checked\)/);
  assert.match(backendSource, /"harmonyPolyLegatoMs": 50\.0/);
  assert.match(backendSource, /"harmonyPolyMergeOctaves": True/);
});
