import { useSyncExternalStore } from "react";
import { en } from "./en.ts";
import { ja, type MessageKey } from "./ja.ts";

export type { MessageKey } from "./ja.ts";
export type Language = "ja" | "en";

const tables: Record<Language, Record<MessageKey, string>> = { ja, en };
let current: Language = "ja";
const listeners = new Set<() => void>();

/** Anything but English reads as Japanese, the app's own language. */
export function normalizeLanguage(value: string | null | undefined): Language {
  return value === "en" ? "en" : "ja";
}

export function getLanguage(): Language {
  return current;
}

/** Switch the screen language; every component using useLanguage redraws. */
export function setLanguage(value: string | null | undefined): void {
  const next = normalizeLanguage(value);
  if (next === current) return;
  current = next;
  if (typeof document !== "undefined") document.documentElement.lang = next;
  for (const listener of listeners) listener();
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

/** The text for ``key`` in the current language; ``{name}`` takes ``params.name``. */
export function t(key: MessageKey, params?: Record<string, string | number>): string {
  const text = tables[current][key] ?? ja[key];
  if (!params) return text;
  return text.replace(/\{(\w+)\}/g, (match, name: string) => (name in params ? String(params[name]) : match));
}

/** Redraw the calling component when the language changes. */
export function useLanguage(): Language {
  return useSyncExternalStore(subscribe, getLanguage, getLanguage);
}
