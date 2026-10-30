/** Reject no-op slider input before App.updateView disables playback follow. */
export function timelineSliderStart(rawStart: number, currentStart: number, maxStart: number): number | null {
  if (!Number.isFinite(rawStart) || !Number.isFinite(currentStart) || !Number.isFinite(maxStart)) return null;
  const limit = Math.max(0, maxStart);
  if (limit === 0) return null;
  const start = Math.max(0, Math.min(limit, rawStart));
  return start === currentStart ? null : start;
}
