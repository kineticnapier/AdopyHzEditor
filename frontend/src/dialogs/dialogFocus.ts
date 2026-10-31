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
