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

/** Preserve the keyboard focus origin when a pointer hovers another open menu.
 * Hover alone must not move focus if the user is working elsewhere.
 */
export function menuHoverFocusOrigin(
  activeMenu: string,
  focused: Pick<Element, "closest"> | null,
): "popup" | "trigger" | null {
  if (focused?.closest(`[data-menu-popup="${activeMenu}"]`)) return "popup";
  if (focused?.closest(`[data-menu-id="${activeMenu}"]`)) return "trigger";
  return null;
}

/** A deferred focus move must not override a control focused after scheduling. */
export function canTransferDeferredMenuFocus(
  previouslyFocused: Element | null,
  currentlyFocused: Element | null,
  body: Element,
  documentElement: Element,
): boolean {
  return !currentlyFocused || currentlyFocused === previouslyFocused ||
    currentlyFocused === body || currentlyFocused === documentElement ||
    !currentlyFocused.isConnected;
}

/** Focus the first enabled item when moving between open popups with Left/Right.
 * From a menu-bar trigger, keep focus on the adjacent trigger instead.
 * Fall back to the trigger if the destination popup has no enabled items.
 */
export function focusAdjacentMenu(
  root: Pick<HTMLElement, "querySelector"> | null,
  id: string,
  preferPopupItem: boolean,
  expectsOpenPopup = false,
): void {
  // A pending animation frame can run after a click, Escape, or blur closes
  // the menu. Never steal focus back to its trigger in that case.
  if (expectsOpenPopup && !root?.querySelector(`[data-menu-popup="${id}"]`)) return;
  const trigger = root?.querySelector<HTMLButtonElement>(`[data-menu-id="${id}"]`);
  const firstItem = preferPopupItem
    ? root?.querySelector<HTMLButtonElement>(`[data-menu-popup="${id}"] button:not(:disabled)`)
    : null;
  (firstItem ?? trigger)?.focus();
}

/** Focus an opened menu after the trigger key, unless focus has moved elsewhere.
 * The popup ref becomes null when the menu closes before the animation frame.
 */
export function focusOpenedMenuEdgeItem(
  popup: Pick<HTMLElement, "querySelectorAll"> | null,
  edge: "first" | "last",
  previouslyFocused: Element | null,
  currentlyFocused: Element | null,
  body: Element,
  documentElement: Element,
): void {
  if (!popup || !canTransferDeferredMenuFocus(previouslyFocused, currentlyFocused, body, documentElement)) return;
  const items = popup.querySelectorAll<HTMLButtonElement>('button:not(:disabled)');
  items[edge === "first" ? 0 : items.length - 1]?.focus();
}

/** Restore menu focus only when closing the popup left focus unclaimed.
 * An action may open a dialog that has already focused its own controls.
 */
export function restoreMenuTriggerFocus(
  root: Pick<HTMLElement, "querySelector"> | null,
  id: string,
  activeElement: Element | null,
  body: Element,
  documentElement: Element,
): void {
  if (activeElement && activeElement !== body && activeElement !== documentElement && activeElement.isConnected) return;
  root?.querySelector<HTMLButtonElement>(`[data-menu-id="${id}"]`)?.focus();
}
