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
