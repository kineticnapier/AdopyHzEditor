import type { ViewState } from "./bridge";
import { wheelViewChange, type WheelPitchAccumulator } from "./wheelNavigation.ts";

/**
 * Keep one native wheel listener mounted while React replaces callbacks and
 * playback data. Refs are updated by the owning component before paint.
 */
export function createCanvasWheelHandler(context: {
  canvas: Pick<HTMLCanvasElement, "getBoundingClientRect">;
  view: { current: ViewState };
  pitchAccumulator: { current: WheelPitchAccumulator };
  activePointerId: { current: number | null };
  duration: { current: number };
  onView: { current: (changes: Partial<ViewState>) => Promise<void> };
}): (event: WheelEvent) => void {
  return (event) => {
    event.preventDefault();
    if (context.activePointerId.current !== null) {
      context.pitchAccumulator.current = { modifier: null, remainder: 0 };
      return;
    }
    const rect = context.canvas.getBoundingClientRect();
    const changes = wheelViewChange(
      event,
      context.view.current,
      {
        timeRatio: Math.max(0, Math.min(1, (event.clientX - rect.left) / Math.max(1, rect.width))),
        pitchRatio: Math.max(0, Math.min(1, (rect.bottom - event.clientY) / Math.max(1, rect.height))),
      },
      context.pitchAccumulator.current,
      context.duration.current,
    );
    if (changes) {
      // Preserve the accumulated view even if React has not rendered yet.
      context.view.current = { ...context.view.current, ...changes };
      void context.onView.current(changes);
    }
  };
}
