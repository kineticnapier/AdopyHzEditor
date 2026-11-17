import type { BackendApi } from "./bridge";
import { dispatchEditorShortcut, type ShortcutActions } from "./shortcutDispatch.ts";
import { isInteractiveShortcutTarget, shouldDispatchEditorShortcut } from "./shortcutTarget.ts";

export type ShortcutListenerState = ShortcutActions & {
  disabled: boolean;
  api: BackendApi | null;
};

/** Consume repeated editing keys so a held key cannot enqueue the same mutation
 * against indices captured before the previous edit completes. Native text
 * inputs are filtered by shouldDispatchEditorShortcut before this check.
 * Undo and navigation remain repeatable.
 */
function isRepeatedMutationShortcut(event: KeyboardEvent): boolean {
  if (!event.repeat || event.getModifierState?.("AltGraph")) return false;
  const key = event.key.toLowerCase();
  const ctrl = event.ctrlKey || event.metaKey;
  if (ctrl) {
    // Ctrl/Meta+Shift+Arrow nudges notes through an asynchronous mutation queue.
    // Unlike navigation arrows, repeating these can enqueue stale note indices.
    if (event.shiftKey) return !event.altKey &&
      (key === "arrowleft" || key === "arrowright" ||
       key === "arrowup" || key === "arrowdown");
    if (event.altKey) return key === "a";
    return key === "x" || key === "v" || key === "d";
  }
  return !event.altKey && !event.shiftKey && key === "q";
}

/** Keep the window listener stable while reading the latest committed editor state. */
export function createEditorShortcutHandler(getCurrent: () => ShortcutListenerState) {
  return (event: KeyboardEvent) => {
    const current = getCurrent();
    if (!current.api || current.disabled) return;
    // The shortcut-target guard rejects repeated Delete/Backspace before
    // dispatch. Consume those repeats on the editor surface so they cannot
    // fall through to the browser, but preserve native input editing.
    const key = event.key.toLowerCase();
    if (event.repeat && (key === "delete" || key === "backspace") &&
        !event.ctrlKey && !event.metaKey && !event.altKey && !event.shiftKey &&
        !event.defaultPrevented && !event.isComposing && event.keyCode !== 229 &&
        !isInteractiveShortcutTarget(event.target)) {
      event.preventDefault();
      return;
    }
    if (!shouldDispatchEditorShortcut(event, current.disabled)) return;
    if (isRepeatedMutationShortcut(event)) {
      event.preventDefault();
      return;
    }
    dispatchEditorShortcut(event, current);
  };
}
