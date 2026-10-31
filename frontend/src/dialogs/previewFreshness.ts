/** A preview may be shown or applied only for the exact current options. */
export function previewIsCurrent<T>(
  preview: T | null,
  previewKey: string,
  optionsKey: string,
): preview is T {
  return preview !== null && previewKey === optionsKey;
}

/** A selection-dependent preview is stale until defaults for the current selection arrive. */
export function selectionScopedPreviewIsCurrent<T>(
  preview: T | null,
  previewKey: string,
  optionsKey: string,
  defaultsSelectionKey: string | null,
  currentSelectionKey: string,
): preview is T {
  return defaultsSelectionKey === currentSelectionKey &&
    previewIsCurrent(preview, previewKey, optionsKey);
}

/** Harmonic defaults must not survive a document/API change with equal note IDs. */
export function harmonicDefaultsContextIsCurrent(
  loaded: { api: object; selected: readonly number[]; attempt: number } | null,
  current: { api: object; selected: readonly number[]; attempt: number },
): boolean {
  return loaded !== null &&
    loaded.api === current.api &&
    loaded.selected === current.selected &&
    loaded.attempt === current.attempt;
}

/** Defaults belong to the exact request context, not just equal note IDs. */
export function exportDefaultsContextIsCurrent(
  loaded: { api: object; selected: readonly number[]; defaultSelectedOnly: boolean; loadAttempt: number } | null,
  current: { api: object; selected: readonly number[]; defaultSelectedOnly: boolean; loadAttempt: number },
): boolean {
  return loaded !== null &&
    loaded.api === current.api &&
    loaded.selected === current.selected &&
    loaded.defaultSelectedOnly === current.defaultSelectedOnly &&
    loaded.loadAttempt === current.loadAttempt;
}
