/** A preview may be shown or applied only for the exact current options. */
export function previewIsCurrent<T>(
  preview: T | null,
  previewKey: string,
  optionsKey: string,
): preview is T {
  return preview !== null && previewKey === optionsKey;
}
