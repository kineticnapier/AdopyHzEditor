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
      item.closest("[inert], [aria-hidden='true']")) return false;
  // visibility:hidden/collapse still has layout rectangles, but is not tabbable.
  // Computed visibility includes inherited visibility from the dialog's ancestors.
  const visibility = item.ownerDocument?.defaultView?.getComputedStyle(item).visibility;
  return visibility === undefined || visibility === "visible";
}

/** A modified Escape is not a request to dismiss the dialog. */
export function isPlainDialogEscape(event: Pick<KeyboardEvent, "key" | "ctrlKey" | "metaKey" | "altKey" | "shiftKey">): boolean {
  return event.key === "Escape" && !event.ctrlKey && !event.metaKey && !event.altKey && !event.shiftKey;
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

/** Only the frontmost modal should respond to Escape or trap Tab.
 * Multiple dialogs can coexist briefly during state transitions.
 */
export function isTopmostDialog(dialog: HTMLElement | null): boolean {
  if (!dialog?.isConnected) return false;
  const dialogs = dialog.ownerDocument.querySelectorAll<HTMLElement>(
    '[role="dialog"][aria-modal="true"]',
  );
  // A hidden or inert modal must not block keyboard handling by a visible one.
  for (let i = dialogs.length - 1; i >= 0; i--) {
    const candidate = dialogs[i];
    if (!candidate.isConnected ||
        !candidate.getClientRects().length ||
        candidate.closest("[inert], [aria-hidden='true']")) continue;
    const visibility = candidate.ownerDocument.defaultView?.getComputedStyle(candidate).visibility;
    if (visibility === "hidden" || visibility === "collapse") continue;
    return candidate === dialog;
  }
  return false;
}

/** Avoid stealing focus from another open modal when a dialog unmounts.
 * When the top modal closes, return focus to the remaining visible modal.
 */
export function dialogFocusRestorationTarget(
  previous: HTMLElement | null,
  closing: HTMLElement | null,
): HTMLElement | null {
  const doc = closing?.ownerDocument ?? previous?.ownerDocument;
  if (!doc) return previous?.isConnected ? previous : null;
  const dialogs = doc.querySelectorAll<HTMLElement>('[role="dialog"][aria-modal="true"]');
  for (let i = dialogs.length - 1; i >= 0; i--) {
    const candidate = dialogs[i];
    if (candidate === closing ||
        !candidate.isConnected ||
        !candidate.getClientRects().length ||
        candidate.closest("[inert], [aria-hidden='true']")) continue;
    const visibility = doc.defaultView?.getComputedStyle(candidate).visibility;
    if (visibility === "hidden" || visibility === "collapse") continue;
    // A background dialog unmounting must not reset focus in the active one.
    if (candidate.contains(doc.activeElement)) return null;
    if (previous?.isConnected && candidate.contains(previous)) return previous;
    const first = Array.from(candidate.querySelectorAll<HTMLElement>(dialogFocusableSelector))
      .find(isDialogTabbable);
    return first ?? candidate;
  }
  return previous?.isConnected ? previous : null;
}
