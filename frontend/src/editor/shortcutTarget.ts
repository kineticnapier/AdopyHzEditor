/** Keydown may target Document/Window or a text node, not only an HTMLElement. */
export function isTextEditingTarget(target: EventTarget | null): boolean {
  const element = target as HTMLElement | null;
  return typeof element?.closest === "function" &&
    Boolean(element.closest("input,select,textarea,[contenteditable='true']"));
}
