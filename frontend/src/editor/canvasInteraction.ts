/** Decide whether Escape cancels a pending gesture or clears an idle selection. */
export function canvasEscapeAction(dragging: boolean): "cancel-drag" | "clear-selection" {
  return dragging ? "cancel-drag" : "clear-selection";
}

/** Clear both selection layers when Escape is pressed without an active drag.
 * Clearing Track first also invalidates an in-flight range lookup in App.
 */
export function clearIdleCanvasSelection(clearTracks: () => void, clearNotes: () => void): void {
  clearTracks();
  clearNotes();
}

/** Only one pointer can own an edit gesture at a time. */
export function canStartCanvasGesture(activePointerId: number | null): boolean {
  return activePointerId === null;
}

/** Ignore move/up/cancel events from another pointer until the owner finishes. */
export function isCanvasGesturePointer(activePointerId: number | null, pointerId: number): boolean {
  return activePointerId === pointerId;
}

/** Release capture only for a pointer that this canvas still owns. */
export function releaseCanvasPointerCapture(
  canvas: Pick<Element, "hasPointerCapture" | "releasePointerCapture">,
  pointerId: number | null,
): boolean {
  if (pointerId === null || !canvas.hasPointerCapture(pointerId)) return false;
  canvas.releasePointerCapture(pointerId);
  return true;
}

/** A held pointer owns the current edit targets. Arrow shortcuts must not
 * change selection, seek, or move notes before that gesture is released. */
export function shouldSuppressCanvasArrowDuringPointerGesture(
  key: string, activePointerId: number | null,
): boolean {
  return activePointerId !== null &&
    (key === "ArrowLeft" || key === "ArrowRight" || key === "ArrowUp" || key === "ArrowDown");
}

/** Report immediately at most once per interval, then deliver the final pointer position.
 * Without a trailing report, a pointer that stops during the throttle window can
 * leave the displayed Track and cursor position stale until the next movement. */
export function createTrailingReporter<T>(
  intervalMs: number,
  now: () => number = () => performance.now(),
  schedule: (callback: () => void, delayMs: number) => number = (callback, delayMs) => window.setTimeout(callback, delayMs),
  cancelTimer: (id: number) => void = id => window.clearTimeout(id),
) {
  let lastReport = -Infinity;
  let timer: number | null = null;
  // Ignore callbacks that were queued before a cancellation or replacement.
  let timerGeneration = 0;
  let pending: { value: T; emit: (value: T) => void } | null = null;
  const flush = () => {
    timer = null;
    const current = pending;
    pending = null;
    if (!current) return;
    lastReport = now();
    current.emit(current.value);
  };
  return {
    report(value: T, emit: (value: T) => void) {
      pending = { value, emit };
      const remaining = intervalMs - (now() - lastReport);
      if (remaining <= 0) {
        if (timer !== null) cancelTimer(timer);
        timerGeneration += 1;
        flush();
      } else if (timer === null) {
        const generation = ++timerGeneration;
        timer = schedule(() => {
          if (generation !== timerGeneration) return;
          timerGeneration += 1;
          flush();
        }, remaining);
      }
    },
    cancel() {
      if (timer !== null) cancelTimer(timer);
      timerGeneration += 1;
      timer = null;
      pending = null;
      // A new pointer session must report its first position immediately.
      lastReport = -Infinity;
    },
  };
}
