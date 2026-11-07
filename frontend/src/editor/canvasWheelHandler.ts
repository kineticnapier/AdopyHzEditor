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

/**
 * A new externally chosen pitch range starts a new fine-wheel gesture.
 * Ignore time-only changes (notably playback follow), and retain carry when
 * React merely acknowledges a wheel change already in the optimistic ref.
 */
export function syncCanvasWheelView(
  view: { current: ViewState },
  carry: { current: WheelPitchAccumulator },
  next: ViewState,
): void {
  if (view.current.pitchBottom !== next.pitchBottom ||
      view.current.visibleNotes !== next.visibleNotes ||
      view.current.mode !== next.mode) {
    carry.current = { modifier: null, remainder: 0 };
  }
  view.current = next;
}

/**
 * Pitch-wheel fractions belong to one held-modifier gesture. Releasing the
 * modifier (or leaving the window) must not carry sub-MIDI steps into a later
 * gesture, even if no ordinary wheel event occurs between them.
 */
export function observeWheelPitchCarryRelease(
  target: Pick<Window, "addEventListener" | "removeEventListener">,
  carry: { current: WheelPitchAccumulator },
  documentTarget?: Pick<Document, "addEventListener" | "removeEventListener" | "visibilityState">,
): () => void {
  const reset = () => {
    carry.current = { modifier: null, remainder: 0 };
  };
  const onKeyUp = (event: KeyboardEvent) => {
    if ((carry.current.modifier === "shift" && event.key === "Shift") ||
        (carry.current.modifier === "alt" && (event.key === "Alt" || event.key === "AltGraph"))) {
      reset();
    }
  };
  const onVisibilityChange = () => {
    // Switching tabs need not fire window blur in every host/browser.
    if (documentTarget?.visibilityState === "hidden") reset();
  };
  target.addEventListener("keyup", onKeyUp);
  target.addEventListener("blur", reset);
  documentTarget?.addEventListener("visibilitychange", onVisibilityChange);
  return () => {
    target.removeEventListener("keyup", onKeyUp);
    target.removeEventListener("blur", reset);
    documentTarget?.removeEventListener("visibilitychange", onVisibilityChange);
  };
}
