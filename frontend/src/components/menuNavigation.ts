/** Ignore browser/OS shortcuts and IME composition in menu navigation. */
export function isPlainMenuNavigationEvent(
  event: Pick<KeyboardEvent, "defaultPrevented"> &
    Partial<Pick<KeyboardEvent, "ctrlKey" | "metaKey" | "altKey" | "shiftKey" | "isComposing" | "keyCode">>,
): boolean {
  return !event.defaultPrevented && !event.ctrlKey && !event.metaKey &&
    !event.altKey && !event.shiftKey && !event.isComposing && event.keyCode !== 229;
}

/** Move between menu-bar triggers, preferring the trigger that actually has focus. */
export function nextMenuId<T extends string>(
  menuIds: readonly T[],
  active: T | null,
  focusedTrigger: T | null,
  direction: "ArrowLeft" | "ArrowRight",
): T | null {
  const current = focusedTrigger ?? active;
  if (!current || menuIds.length === 0) return null;
  const index = menuIds.indexOf(current);
  if (index < 0) return null;
  const step = direction === "ArrowRight" ? 1 : -1;
  return menuIds[(index + step + menuIds.length) % menuIds.length];
}
