import type { ViewState } from "./bridge";

/** Match the Python view bounds before an optimistic canvas update. */
export function clampPitchViewChange(
  view: ViewState,
  changes: Partial<ViewState>,
): Partial<ViewState> {
  if (changes.pitchBottom === undefined && changes.visibleNotes === undefined) return changes;
  const visibleNotes = Math.max(6, Math.min(128, Math.round(changes.visibleNotes ?? view.visibleNotes)));
  const pitchBottom = Math.max(0, Math.min(128 - visibleNotes, Math.round(changes.pitchBottom ?? view.pitchBottom)));
  return {
    ...changes,
    ...(changes.visibleNotes === undefined ? {} : { visibleNotes }),
    pitchBottom,
  };
}
