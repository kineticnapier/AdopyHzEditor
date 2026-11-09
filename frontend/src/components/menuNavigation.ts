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

/** Focus the first enabled item when moving between open popups with Left/Right.
 * From a menu-bar trigger, keep focus on the adjacent trigger instead.
 * Fall back to the trigger if the destination popup has no enabled items.
 */
export function focusAdjacentMenu(root: Pick<HTMLElement, "querySelector"> | null, id: string, preferPopupItem: boolean): void {
  const trigger = root?.querySelector<HTMLButtonElement>(`[data-menu-id="${id}"]`);
  const firstItem = preferPopupItem
    ? root?.querySelector<HTMLButtonElement>(`[data-menu-popup="${id}"] button:not(:disabled)`)
    : null;
  (firstItem ?? trigger)?.focus();
}
