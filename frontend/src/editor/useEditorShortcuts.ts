import { useEffect } from "react";
import type { BackendApi } from "./bridge";
import { dispatchEditorShortcut, type ShortcutActions } from "./shortcutDispatch";

function isInteractiveTarget(target: EventTarget | null) {
  const element = target as HTMLElement | null;
  return Boolean(element?.closest("input,select,textarea,button,a,[contenteditable='true'],[role='dialog']"));
}

type Args = ShortcutActions & {
  disabled: boolean;
  api: BackendApi | null;
};

export default function useEditorShortcuts(a: Args) {
  useEffect(() => {
    if (!a.api) return;
    const handler = (event: KeyboardEvent) => {
      if (a.disabled || isInteractiveTarget(event.target)) return;
      dispatchEditorShortcut(event, a);
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [a]);
}
