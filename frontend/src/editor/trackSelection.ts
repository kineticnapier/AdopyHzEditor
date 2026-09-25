export type TrackSelectionRange = {
  startTime: number;
  endTime: number;
  minMidi: number;
  maxMidi: number;
};

export function normalizeTrackRange(
  startTime: number,
  endTime: number,
  firstMidi: number,
  secondMidi: number,
): TrackSelectionRange {
  return {
    startTime: Math.min(startTime, endTime),
    endTime: Math.max(startTime, endTime),
    minMidi: Math.min(firstMidi, secondMidi),
    maxMidi: Math.max(firstMidi, secondMidi),
  };
}

export function updateTrackSelection(current: number[], trackId: number, additive: boolean): number[] {
  if (!additive) return [trackId];
  if (current.includes(trackId)) return current.filter(id => id !== trackId);
  return [...current, trackId].sort((a, b) => a - b);
}

export function mergeTrackSelection(current: number[], incoming: number[], additive: boolean): number[] {
  const next = additive ? [...current, ...incoming] : [...incoming];
  return Array.from(new Set(next)).sort((a, b) => a - b);
}
