import { useEffect } from "react";
import type { BackendApi } from "./bridge";
import { dispatchEditorShortcut, type ShortcutActions } from "./shortcutDispatch";

function isTextEditingTarget(target: EventTarget | null) {
  const element = target as HTMLElement | null;
  return Boolean(element?.closest("input,select,textarea,[contenteditable='true']"));
}

type Args = ShortcutActions & {
  disabled: boolean;
  api: BackendApi | null;
};

export default function useEditorShortcuts(a: Args) {
  useEffect(() => {
    if (!a.api) return;
    const handler = (event: KeyboardEvent) => {
      if (event.defaultPrevented) return;
      if (a.disabled) return;
      const key=event.key.toLowerCase(),ctrl=event.ctrlKey||event.metaKey;
      if(event.repeat&&(key==="delete"||key==="backspace"))return;
      if(isTextEditingTarget(event.target)&&!(key==="f1"||(ctrl&&key==="s")))return;
      dispatchEditorShortcut(event, a);
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [a]);
}
