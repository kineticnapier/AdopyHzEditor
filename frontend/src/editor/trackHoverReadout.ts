export type TrackHoverReadout = {
  id: number;
  noteName: string;
  duration: number;
  magnitude: number;
};

export function formatTrackHoverReadout(track: TrackHoverReadout): string {
  return `Track #${track.id} · ${track.noteName} · ${track.duration.toFixed(3)} s · ${(track.magnitude * 100).toFixed(1)}%`;
}
