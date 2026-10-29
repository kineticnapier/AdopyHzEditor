/** Decide whether Escape cancels a pending gesture or clears an idle selection. */
export function canvasEscapeAction(dragging: boolean): "cancel-drag" | "clear-selection" {
  return dragging ? "cancel-drag" : "clear-selection";
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
