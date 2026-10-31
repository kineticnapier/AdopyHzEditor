/** Native controls must receive Space, arrows and other unmodified keys before editor shortcuts. */
export function isInteractiveShortcutTarget(target: EventTarget | null): boolean {
  const element = target as HTMLElement | null;
  return typeof element?.closest === "function" &&
    Boolean(element.closest("input,select,textarea,button,a,[contenteditable='true'],[contenteditable=''],[contenteditable='plaintext-only'],[role='button'],[role='menuitem'],[role='menu'],[role='dialog'],[role='slider'],[role='textbox'],[role='spinbutton'],[role='combobox'],[role='listbox'],[role='checkbox'],[role='radio'],[role='switch']"));
}

/** Ctrl/Meta+S must still commit a focused numeric field before saving. */
export function shouldDispatchEditorShortcut(
  event: Pick<KeyboardEvent, "target" | "key" | "ctrlKey" | "metaKey" | "repeat" | "defaultPrevented">,
  disabled: boolean,
): boolean {
  if (event.defaultPrevented || disabled) return false;
  const key = event.key.toLowerCase();
  if (event.repeat && (key === "delete" || key === "backspace")) return false;
  return !isInteractiveShortcutTarget(event.target) ||
    key === "f1" || ((event.ctrlKey || event.metaKey) && key === "s");
}
