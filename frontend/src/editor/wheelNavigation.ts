import type { ViewState } from "./bridge";

export type WheelInput = Pick<
  WheelEvent,
  "deltaX" | "deltaY" | "deltaMode" | "shiftKey" | "altKey" | "ctrlKey"
>;

/** Horizontal gestures pan in their actual direction; vertical wheel controls retain existing behavior. */
export function wheelViewChange(event: WheelInput, view: ViewState): Partial<ViewState> | null {
  const { deltaX, deltaY } = event;
  if (deltaX === 0 && deltaY === 0) return null;

  // Trackpads may report both axes; the dominant axis determines the action.
  // Treat a horizontal-only Ctrl/Alt/Shift gesture as panning, not zooming.
  if (Math.abs(deltaX) > Math.abs(deltaY)) {
    const units = event.deltaMode === 1 ? deltaX / 3 : event.deltaMode === 2 ? deltaX : deltaX / 120;
    return { start: view.start + units * view.windowSeconds * .08 };
  }

  const sign = deltaY < 0 ? 1 : -1;
  if (event.shiftKey) {
    const maxBottom = Math.max(0, 128 - view.visibleNotes);
    return { pitchBottom: Math.max(0, Math.min(maxBottom, view.pitchBottom + sign * 3)) };
  }
  if (event.altKey) {
    const visibleNotes = Math.max(6, Math.min(128, view.visibleNotes - sign * 4));
    const pitchBottom = Math.max(0, Math.min(view.pitchBottom, 128 - visibleNotes));
    return { visibleNotes, pitchBottom };
  }
  if (event.ctrlKey) return { windowSeconds: view.windowSeconds * (sign > 0 ? .85 : 1.18) };
  return { start: view.start - sign * view.windowSeconds * .08 };
}
