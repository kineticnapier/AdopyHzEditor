import type { ViewState } from "./bridge";

/** Convert wheel pixels, lines and pages to the same nominal wheel tick. */
function wheelTicks(delta: number, deltaMode: number): number {
  return deltaMode === 1 ? delta / 3 : deltaMode === 2 ? delta : delta / 120;
}

export type WheelInput = Pick<
  WheelEvent,
  "deltaX" | "deltaY" | "deltaMode" | "shiftKey" | "altKey" | "ctrlKey"
>;

/** Preserve sub-note wheel movement until it becomes a whole MIDI step. */
export type WheelPitchAccumulator = {
  modifier: "shift" | "alt" | null;
  remainder: number;
};

function pitchWheelSteps(
  delta: number,
  modifier: "shift" | "alt",
  accumulator?: WheelPitchAccumulator,
): number {
  if (!accumulator) return Math.trunc(delta);
  if (accumulator.modifier !== modifier) {
    accumulator.modifier = modifier;
    accumulator.remainder = 0;
  }
  const total = accumulator.remainder + delta;
  // Allow for floating-point error after many tiny trackpad events.
  const steps = total < 0 ? Math.ceil(total - 1e-10) : Math.floor(total + 1e-10);
  accumulator.remainder = total - steps;
  return steps;
}

/** Horizontal gestures pan in their actual direction; vertical wheel controls retain existing behavior. */
export function wheelViewChange(
  event: WheelInput,
  view: ViewState,
  anchor?: {timeRatio:number;pitchRatio:number},
  pitchAccumulator?: WheelPitchAccumulator,
): Partial<ViewState> | null {
  const { deltaX, deltaY } = event;
  const resetPitchAccumulator = () => {
    if (pitchAccumulator) {
      pitchAccumulator.modifier = null;
      pitchAccumulator.remainder = 0;
    }
  };
  if (deltaX === 0 && deltaY === 0) return null;

  // Trackpads may report both axes; the dominant axis determines the action.
  // Treat a horizontal-only Ctrl/Alt/Shift gesture as panning, not zooming.
  if (Math.abs(deltaX) > Math.abs(deltaY)) {
    resetPitchAccumulator();
    const units = wheelTicks(deltaX, event.deltaMode);
    return { start: view.start + units * view.windowSeconds * .08 };
  }

  const units = wheelTicks(deltaY, event.deltaMode);
  if (event.shiftKey) {
    const steps = pitchWheelSteps(-3 * units, "shift", pitchAccumulator);
    if (steps === 0) return null;
    const maxBottom = Math.max(0, 128 - view.visibleNotes);
    const pitchBottom = Math.max(0, Math.min(maxBottom, view.pitchBottom + steps));
    if (pitchAccumulator && pitchBottom === view.pitchBottom) pitchAccumulator.remainder = 0;
    return { pitchBottom };
  }
  if (event.altKey) {
    const steps = pitchWheelSteps(4 * units, "alt", pitchAccumulator);
    if (steps === 0) return null;
    const visibleNotes = Math.max(6, Math.min(128, view.visibleNotes + steps));
    if (pitchAccumulator && visibleNotes === view.visibleNotes) pitchAccumulator.remainder = 0;
    if(!anchor){
      return {visibleNotes,pitchBottom:Math.max(0,Math.min(view.pitchBottom,128-visibleNotes))};
    }
    const midi = view.pitchBottom - .5 + anchor.pitchRatio * view.visibleNotes;
    const pitchBottom = Math.max(0, Math.min(midi + .5 - anchor.pitchRatio * visibleNotes, 128 - visibleNotes));
    return { visibleNotes, pitchBottom };
  }
  resetPitchAccumulator();
  if (event.ctrlKey) {
    // High-resolution trackpads emit many small deltas: zoom proportionally, not once per event.
    // Use reciprocal zoom factors so an equal reverse gesture restores the viewport.
    const windowSeconds=view.windowSeconds*Math.pow(.85,-units);
    if(!anchor)return {windowSeconds};
    const time=view.start+anchor.timeRatio*view.windowSeconds;
    return {windowSeconds,start:time-anchor.timeRatio*windowSeconds};
  }
  return { start: view.start + units * view.windowSeconds * .08 };
}
