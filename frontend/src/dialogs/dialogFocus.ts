/** Keyboard-focusable controls, including native <summary> and links inside dialogs. */
export const dialogFocusableSelector = [
  "a[href]",
  "area[href]",
  "summary",
  "button:not(:disabled)",
  "input:not(:disabled)",
  "select:not(:disabled)",
  "textarea:not(:disabled)",
  "[tabindex]:not([tabindex='-1'])",
].join(",");

/** Only truly keyboard-reachable elements should participate in the dialog Tab trap.
 * :disabled also covers inputs disabled by an ancestor <fieldset disabled>.
 * An inert subtree is not keyboard-reachable even when it remains laid out.
 */
export function isDialogTabbable(item: HTMLElement): boolean {
  if (!item.getClientRects().length ||
      item.tabIndex < 0 ||
      item.matches(":disabled") ||
      item.closest("[inert]")) return false;
  // visibility:hidden/collapse still has layout rectangles, but is not tabbable.
  // Computed visibility includes inherited visibility from the dialog's ancestors.
  const visibility = item.ownerDocument?.defaultView?.getComputedStyle(item).visibility;
  return visibility === undefined || visibility === "visible";
}

/** Escape/Tab belong to the IME while a composition is in progress.
 * Some Windows IMEs emit keyCode 229 even when isComposing is false.
 */
export function isDialogCompositionKey(event: Pick<KeyboardEvent, "isComposing" | "keyCode">): boolean {
  return event.isComposing || event.keyCode === 229;
}

/** Select the element that keeps Tab focus inside a dialog at its boundaries. */
export function dialogTabDestination<T extends { focus(): void }>(
  items: readonly T[],
  active: T | null,
  backwards: boolean,
): T | null {
  if (!items.length) return null;
  if (backwards) {
    return active === items[0] || !items.includes(active as T)
      ? items[items.length - 1]
      : null;
  }
  return active === items[items.length - 1] || !items.includes(active as T)
    ? items[0]
    : null;
}
