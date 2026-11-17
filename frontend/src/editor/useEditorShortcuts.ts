import { useEffect, useLayoutEffect, useRef } from "react";
import { createEditorShortcutHandler, type ShortcutListenerState } from "./shortcutListener";

export default function useEditorShortcuts(a: ShortcutListenerState) {
  const latestArgs = useRef(a);
  // A new action object is passed on every App render. Update the handler's
  // state before browser input can be dispatched for the committed UI.
  useLayoutEffect(() => {
    latestArgs.current = a;
  }, [a]);

  useEffect(() => {
    const handler = createEditorShortcutHandler(() => latestArgs.current);
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, []);
}
