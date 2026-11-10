/** Auto-repeated Escape must not clear a selection after its first press
 * has already cancelled pointer capture. The canvas consumes repeat events. */
export function shouldIgnoreRepeatedCanvasEscape(
  event: Pick<KeyboardEvent, "key" | "repeat">,
): boolean {
  return event.key === "Escape" && event.repeat;
}

/** A held pointer must be cancellable even if Ctrl/Shift/Alt/Meta is still
 * pressed. Without a pointer, modified Escape keeps its shortcut semantics. */
export function shouldHandleCanvasEscape(
  event: Pick<KeyboardEvent, "key" | "ctrlKey" | "metaKey" | "altKey" | "shiftKey">,
  activePointerId: number | null,
): boolean {
  return event.key === "Escape" &&
    (activePointerId !== null ||
      (!event.ctrlKey && !event.metaKey && !event.altKey && !event.shiftKey));
}

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

/** While the canvas owns a pointer gesture, other editor shortcuts must not
 * mutate the captured note indices (or replace the document). Escape still
 * cancels the gesture; Tab and modifier keys keep their native behavior.
 * Arrow keys are handled separately by shouldSuppressCanvasArrowDuringPointerGesture.
 */
export function shouldSuppressCanvasNonArrowKeyDuringPointerGesture(
  key: string, activePointerId: number | null,
): boolean {
  if (activePointerId === null) return false;
  return ![
    "Escape", "Tab", "Control", "Shift", "Alt", "Meta",
    "ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown",
  ].includes(key);
}

/** A view change can invalidate the coordinate mapping of an active drag.
 * Playback follow can change start even when the user does not scroll.
 */
export type CanvasGestureView = {
  start: number;
  windowSeconds: number;
  pitchBottom: number;
  visibleNotes: number;
  mode: string;
};

export function shouldCancelCanvasGestureForViewChange(
  activePointerId: number | null,
  previous: CanvasGestureView,
  next: CanvasGestureView,
): boolean {
  return activePointerId !== null &&
    (previous.start !== next.start ||
      previous.windowSeconds !== next.windowSeconds ||
      previous.pitchBottom !== next.pitchBottom ||
      previous.visibleNotes !== next.visibleNotes ||
      previous.mode !== next.mode);
}

/** A new notes array invalidates the indices captured by an active gesture. */
export function shouldCancelCanvasGestureForNotesChange(
  activePointerId: number | null,
  previous: readonly unknown[],
  next: readonly unknown[],
): boolean {
  return activePointerId !== null && previous !== next;
}

/** Ignore duplicate ResizeObserver measurements before publishing React state. */
export function hasCanvasSizeChanged(
  previous: { width: number; height: number },
  next: { width: number; height: number },
): boolean {
  return previous.width !== next.width || previous.height !== next.height;
}

/** Resizing the canvas changes pointer-to-note coordinates during an active edit. */
export function shouldCancelCanvasGestureForResize(
  activePointerId: number | null,
  previous: { width: number; height: number },
  next: { width: number; height: number },
): boolean {
  return activePointerId !== null && hasCanvasSizeChanged(previous, next);
}

type PageExitEventTarget = Pick<EventTarget, "addEventListener" | "removeEventListener">;

/** Cancel an active canvas gesture when the window loses focus or the page is hidden. */
export function observeCanvasPageExit(
  windowTarget: PageExitEventTarget,
  documentTarget: PageExitEventTarget & { readonly visibilityState: string },
  cancelGesture: () => void,
): () => void {
  const onWindowBlur = () => cancelGesture();
  const onVisibilityChange = () => {
    if (documentTarget.visibilityState === "hidden") cancelGesture();
  };
  windowTarget.addEventListener("blur", onWindowBlur);
  documentTarget.addEventListener("visibilitychange", onVisibilityChange);
  return () => {
    windowTarget.removeEventListener("blur", onWindowBlur);
    documentTarget.removeEventListener("visibilitychange", onVisibilityChange);
  };
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
