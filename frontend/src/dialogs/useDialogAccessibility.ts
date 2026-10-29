import { useEffect, useId, useRef } from "react";
import { dialogTabDestination } from "./dialogFocus";

const focusableSelector = [
  "button:not(:disabled)",
  "input:not(:disabled)",
  "select:not(:disabled)",
  "textarea:not(:disabled)",
  "[tabindex]:not([tabindex='-1'])",
].join(",");

export function useDialogAccessibility(onClose: () => void) {
  const dialogRef = useRef<HTMLElement>(null), titleId = useId(), closeRef = useRef(onClose);
  closeRef.current = onClose;
  useEffect(() => {
    const previous = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const dialog = dialogRef.current;
    const focusable = () => Array.from(dialog?.querySelectorAll<HTMLElement>(focusableSelector) ?? [])
      .filter(item => item.getClientRects().length > 0);
    const frame = window.requestAnimationFrame(() => {
      if (dialog?.isConnected) (focusable()[0] ?? dialog).focus();
    });
    const key = (event: KeyboardEvent) => {
      if (event.defaultPrevented) return;
      if (event.key === "Escape") {
        event.preventDefault();
        closeRef.current();
        return;
      }
      if (event.key !== "Tab" || !dialog) return;
      const items = focusable();
      if (!items.length) {
        event.preventDefault();
        dialog.focus();
        return;
      }
      const destination = dialogTabDestination(items, document.activeElement as HTMLElement | null, event.shiftKey);
      if (destination) {
        event.preventDefault();
        destination.focus();
      }
    };
    window.addEventListener("keydown", key);
    return () => {
      window.cancelAnimationFrame(frame);
      window.removeEventListener("keydown", key);
      if (previous?.isConnected) previous.focus();
    };
  }, []);
  return { dialogRef, titleId };
}
