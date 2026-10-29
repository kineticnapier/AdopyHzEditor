/** Decide whether Escape cancels a pending gesture or clears an idle selection. */
export function canvasEscapeAction(dragging: boolean): "cancel-drag" | "clear-selection" {
  return dragging ? "cancel-drag" : "clear-selection";
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
