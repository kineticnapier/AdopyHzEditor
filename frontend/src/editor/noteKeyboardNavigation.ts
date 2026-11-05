/** Ctrl/Meta/Alt arrows are reserved for global editor or native shortcuts. */
export function isNoteNavigationKey(
  event: Pick<KeyboardEvent, "key" | "ctrlKey" | "metaKey" | "altKey">,
): boolean {
  return !event.ctrlKey && !event.metaKey && !event.altKey &&
    (event.key === "ArrowLeft" || event.key === "ArrowRight");
}

/** Keep the active end of a keyboard range, but follow external selection changes. */
export function reconcileKeyboardNote(
  focused: number | null,
  previousSelection: readonly number[],
  keyboardSelection: readonly number[] | null,
  selected: readonly number[],
  noteCount: number,
  notesChanged: boolean,
): number | null {
  const same = (a: readonly number[] | null, b: readonly number[]) =>
    a !== null && a.length === b.length && a.every((index, i) => index === b[i]);
  const preserveFocus = same(keyboardSelection, selected) ||
    (!notesChanged && same(previousSelection, selected));
  if (preserveFocus && focused !== null && focused >= 0 && focused < noteCount)
    return focused;
  const lastSelected = selected.at(-1);
  return lastSelected !== undefined && lastSelected >= 0 && lastSelected < noteCount
    ? lastSelected : null;
}

/** Select the contiguous time-ordered range from a fixed keyboard anchor.
 * Returning sorted indices keeps the editor's selection representation stable. */
export function keyboardRangeSelection(order: readonly number[], anchor: number, active: number): number[] {
  const anchorPosition = order.indexOf(anchor), activePosition = order.indexOf(active);
  if (activePosition < 0) return [];
  if (anchorPosition < 0) return [active];
  return order.slice(Math.min(anchorPosition, activePosition), Math.max(anchorPosition, activePosition) + 1)
    .sort((a, b) => a - b);
}
