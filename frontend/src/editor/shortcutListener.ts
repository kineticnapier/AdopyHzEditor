import type { BackendApi } from "./bridge";
import { dispatchEditorShortcut, type ShortcutActions } from "./shortcutDispatch.ts";
import { shouldDispatchEditorShortcut } from "./shortcutTarget.ts";

export type ShortcutListenerState = ShortcutActions & {
  disabled: boolean;
  api: BackendApi | null;
};

/** Keep the window listener stable while reading the latest committed editor state. */
export function createEditorShortcutHandler(getCurrent: () => ShortcutListenerState) {
  return (event: KeyboardEvent) => {
    const current = getCurrent();
    if (!current.api || !shouldDispatchEditorShortcut(event, current.disabled)) return;
    dispatchEditorShortcut(event, current);
  };
}
