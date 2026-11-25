// Mirrors web/adofai.py beat_synced_output_bpm: the output BPM that makes one
// ratio-polyrhythm cycle (cycleAngle degrees) last beatsPerCycle song beats.
export function beatSyncedOutputBpm(songBpm: number, cycleAngle: number, beatsPerCycle: number): number {
  if (!(songBpm > 0) || !(cycleAngle > 0) || !(beatsPerCycle > 0)) return NaN;
  return (cycleAngle * songBpm) / (180 * beatsPerCycle);
}
