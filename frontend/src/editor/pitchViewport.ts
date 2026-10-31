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

/** A note at the upper edge is outside the half-open MIDI viewport. */
export function pitchBottomToRevealNote(
  view: Pick<ViewState, "pitchBottom" | "visibleNotes">,
  midi: number,
): number | null {
  if (midi >= view.pitchBottom && midi < view.pitchBottom + view.visibleNotes) return null;
  return Math.max(0, Math.min(128 - view.visibleNotes, Math.round(midi - view.visibleNotes / 2)));
}

/** Skip view writes that cannot change any displayed value. */
export function hasEffectiveViewChange(view: ViewState, changes: Partial<ViewState>): boolean {
  return (Object.keys(changes) as Array<keyof ViewState>).some(key => changes[key] !== view[key]);
}
