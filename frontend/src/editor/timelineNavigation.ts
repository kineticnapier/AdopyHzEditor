import type { ViewState } from "./bridge";

/** Reject no-op slider input before App.updateView disables playback follow. */
/** Keep the HTML range bounds finite even if playback metadata is invalid. */
export function timelineSliderBounds(
  durationSeconds: number,
  windowSeconds: number,
  currentStart: number,
): { max: number; value: number } {
  const rawMax = durationSeconds - windowSeconds;
  // A negative duration or a window below the backend's 0.2 s minimum
  // is invalid metadata, not an opportunity to pan past the audio.
  const validBounds = Number.isFinite(durationSeconds) && durationSeconds >= 0
    && Number.isFinite(windowSeconds) && windowSeconds >= 0.2;
  const max = validBounds && Number.isFinite(rawMax) ? Math.max(0, rawMax) : 0;
  const value = Number.isFinite(currentStart) ? Math.max(0, Math.min(currentStart, max)) : 0;
  return { max, value };
}

/** Keep the HTML number input's max finite while audio metadata is loading or invalid. */
export function timelineWindowInputMax(durationSeconds: number, currentWindowSeconds: number): number {
  if (Number.isFinite(durationSeconds) && durationSeconds >= 0) return Math.max(0.2, durationSeconds);
  return Number.isFinite(currentWindowSeconds) ? Math.max(0.2, currentWindowSeconds) : 0.2;
}

export function timelineSliderStart(rawStart: number, currentStart: number, maxStart: number): number | null {
  if (!Number.isFinite(rawStart) || !Number.isFinite(currentStart) || !Number.isFinite(maxStart)) return null;
  const limit = Math.max(0, maxStart);
  if (limit === 0) return null;
  const start = Math.max(0, Math.min(limit, rawStart));
  return start === currentStart ? null : start;
}

/** Match Bridge.set_view time bounds before optimistic rendering or follow changes. */
export function clampTimeViewChange(
  view: ViewState,
  changes: Partial<ViewState>,
  durationSeconds: number,
): Partial<ViewState> {
  if (changes.start === undefined && changes.windowSeconds === undefined) return changes;
  const duration = Number.isFinite(durationSeconds)
    ? Math.max(0, durationSeconds)
    : Math.max(0, view.start + view.windowSeconds);
  const requestedWindow = changes.windowSeconds ?? view.windowSeconds;
  const windowSeconds = Math.max(
    0.2,
    Math.min(Math.max(0.2, duration), Number.isFinite(requestedWindow) ? requestedWindow : view.windowSeconds),
  );
  const requestedStart = changes.start ?? view.start;
  const maxStart = Math.max(0, duration - windowSeconds);
  const start = Math.max(0, Math.min(maxStart, Number.isFinite(requestedStart) ? requestedStart : view.start));
  return {
    ...changes,
    ...(changes.windowSeconds === undefined ? {} : { windowSeconds }),
    ...(changes.start !== undefined || start !== view.start ? { start } : {}),
  };
}
