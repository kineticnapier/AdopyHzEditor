import type { ViewState } from "./bridge";

/** Convert wheel pixels, lines and pages to the same nominal wheel tick. */
function wheelTicks(delta: number, deltaMode: number): number {
  return deltaMode === 1 ? delta / 3 : deltaMode === 2 ? delta : delta / 120;
}

export type WheelInput = Pick<
  WheelEvent,
  "deltaX" | "deltaY" | "deltaMode" | "shiftKey" | "altKey" | "ctrlKey"
>;

/** Horizontal gestures pan in their actual direction; vertical wheel controls retain existing behavior. */
export function wheelViewChange(
  event: WheelInput,
  view: ViewState,
  anchor?: {timeRatio:number;pitchRatio:number},
): Partial<ViewState> | null {
  const { deltaX, deltaY } = event;
  if (deltaX === 0 && deltaY === 0) return null;

  // Trackpads may report both axes; the dominant axis determines the action.
  // Treat a horizontal-only Ctrl/Alt/Shift gesture as panning, not zooming.
  if (Math.abs(deltaX) > Math.abs(deltaY)) {
    const units = wheelTicks(deltaX, event.deltaMode);
    return { start: view.start + units * view.windowSeconds * .08 };
  }

  const units = wheelTicks(deltaY, event.deltaMode);
  const sign = deltaY < 0 ? 1 : -1;
  if (event.shiftKey) {
    const maxBottom = Math.max(0, 128 - view.visibleNotes);
    return { pitchBottom: Math.max(0, Math.min(maxBottom, view.pitchBottom + sign * 3)) };
  }
  if (event.altKey) {
    const visibleNotes = Math.max(6, Math.min(128, view.visibleNotes - sign * 4));
    if(!anchor){
      return {visibleNotes,pitchBottom:Math.max(0,Math.min(view.pitchBottom,128-visibleNotes))};
    }
    const midi = view.pitchBottom - .5 + anchor.pitchRatio * view.visibleNotes;
    const pitchBottom = Math.max(0, Math.min(midi + .5 - anchor.pitchRatio * visibleNotes, 128 - visibleNotes));
    return { visibleNotes, pitchBottom };
  }
  if (event.ctrlKey) {
    // High-resolution trackpads emit many small deltas: zoom proportionally, not once per event.
    const windowSeconds=view.windowSeconds*(units<0?Math.pow(.85,-units):Math.pow(1.18,units));
    if(!anchor)return {windowSeconds};
    const time=view.start+anchor.timeRatio*view.windowSeconds;
    return {windowSeconds,start:time-anchor.timeRatio*windowSeconds};
  }
  return { start: view.start + units * view.windowSeconds * .08 };
}
