/** Consume Escape for an open application menu before editor shortcuts run. */
export function consumeMenuEscape<T extends string>(
  event: Pick<KeyboardEvent, "key" | "preventDefault" | "defaultPrevented">,
  activeMenu: T | null,
  close: (id: T) => void,
): boolean {
  if (activeMenu === null || event.key !== "Escape" || event.defaultPrevented) return false;
  event.preventDefault();
  close(activeMenu);
  return true;
}
