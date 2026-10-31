import { useEffect } from "react";
import type { BackendApi } from "./bridge";
import { dispatchEditorShortcut, type ShortcutActions } from "./shortcutDispatch";
import { shouldDispatchEditorShortcut } from "./shortcutTarget";

type Args = ShortcutActions & {
  disabled: boolean;
  api: BackendApi | null;
};

export default function useEditorShortcuts(a: Args) {
  useEffect(() => {
    if (!a.api) return;
    const handler = (event: KeyboardEvent) => {
      if (!shouldDispatchEditorShortcut(event, a.disabled)) return;
      dispatchEditorShortcut(event, a);
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [a]);
}
