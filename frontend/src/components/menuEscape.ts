/** Consume only a plain Escape for an open application menu before editor shortcuts run. */
export function consumeMenuEscape<T extends string>(
  event: Pick<KeyboardEvent, "key" | "preventDefault" | "defaultPrevented"> &
    Partial<Pick<KeyboardEvent, "ctrlKey" | "metaKey" | "altKey" | "shiftKey" | "isComposing" | "keyCode">>,
  activeMenu: T | null,
  close: (id: T) => void,
): boolean {
  // Modified Escape and IME conversion keys belong to the OS/input method.
  if (activeMenu === null || event.key !== "Escape" || event.defaultPrevented ||
      event.ctrlKey || event.metaKey || event.altKey || event.shiftKey ||
      event.isComposing || event.keyCode === 229) return false;
  event.preventDefault();
  close(activeMenu);
  return true;
}
