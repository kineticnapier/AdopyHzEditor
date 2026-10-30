import { useEffect } from "react";
import type { BackendApi } from "./bridge";
import { dispatchEditorShortcut, type ShortcutActions } from "./shortcutDispatch";
import { isTextEditingTarget } from "./shortcutTarget";

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
