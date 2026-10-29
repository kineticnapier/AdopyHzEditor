/** Ctrl/Meta/Alt arrows are reserved for global editor or native shortcuts. */
export function isNoteNavigationKey(
  event: Pick<KeyboardEvent, "key" | "ctrlKey" | "metaKey" | "altKey">,
): boolean {
  return !event.ctrlKey && !event.metaKey && !event.altKey &&
    (event.key === "ArrowLeft" || event.key === "ArrowRight");
}
