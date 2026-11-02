import type { ViewState } from "./bridge";
import { roundToNearestEven } from "../settings/numericInputModel.ts";

/** Match the Python view bounds before an optimistic canvas update. */
export function clampPitchViewChange(
  view: ViewState,
  changes: Partial<ViewState>,
): Partial<ViewState> {
  if (changes.pitchBottom === undefined && changes.visibleNotes === undefined) return changes;
  // Invalid values must not reach optimistic state or the Python set_view API.
  // Time viewport changes already apply the same finite-number guard.
  const requestedVisibleNotes = changes.visibleNotes ?? view.visibleNotes;
  const requestedPitchBottom = changes.pitchBottom ?? view.pitchBottom;
  const visibleNotes = Math.max(6, Math.min(128, roundToNearestEven(
    Number.isFinite(requestedVisibleNotes) ? requestedVisibleNotes : view.visibleNotes,
  )));
  const pitchBottom = Math.max(0, Math.min(128 - visibleNotes, roundToNearestEven(
    Number.isFinite(requestedPitchBottom) ? requestedPitchBottom : view.pitchBottom,
  )));
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
  if (!Number.isFinite(midi)) return null;
  if (midi >= view.pitchBottom && midi < view.pitchBottom + view.visibleNotes) return null;
  return Math.max(0, Math.min(128 - view.visibleNotes, roundToNearestEven(midi - view.visibleNotes / 2)));
}

/** Skip view writes that cannot change any displayed value. */
export function hasEffectiveViewChange(view: ViewState, changes: Partial<ViewState>): boolean {
  return (Object.keys(changes) as Array<keyof ViewState>).some(key => changes[key] !== view[key]);
}
