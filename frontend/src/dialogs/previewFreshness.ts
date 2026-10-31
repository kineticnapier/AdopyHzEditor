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
  loaded: { api: object; selected: readonly number[]; attempt: number; documentGeneration: number } | null,
  current: { api: object; selected: readonly number[]; attempt: number; documentGeneration: number },
): boolean {
  return loaded !== null &&
    loaded.api === current.api &&
    loaded.selected === current.selected &&
    loaded.attempt === current.attempt &&
    loaded.documentGeneration === current.documentGeneration;
}

/** Defaults belong to the exact request context, not just equal note IDs. */
export function exportDefaultsContextIsCurrent(
  loaded: { api: object; selected: readonly number[]; defaultSelectedOnly: boolean; loadAttempt: number; documentGeneration: number } | null,
  current: { api: object; selected: readonly number[]; defaultSelectedOnly: boolean; loadAttempt: number; documentGeneration: number },
): boolean {
  return loaded !== null &&
    loaded.api === current.api &&
    loaded.selected === current.selected &&
    loaded.defaultSelectedOnly === current.defaultSelectedOnly &&
    loaded.loadAttempt === current.loadAttempt &&
    loaded.documentGeneration === current.documentGeneration;
}

/** Blank workspace defaults must belong to the current API and retry. */
export function blankWorkspaceDefaultsContextIsCurrent(
  loaded: { api: object; attempt: number } | null,
  current: { api: object; attempt: number },
): boolean {
  return loaded !== null && loaded.api === current.api && loaded.attempt === current.attempt;
}

/** A Quick Hz preview must come from the current backend, not only matching options. */
export function quickHzPreviewIsCurrent<T>(
  preview: T | null,
  previewKey: string,
  optionsKey: string,
  previewApi: object | null,
  currentApi: object,
): preview is T {
  return previewApi === currentApi && previewIsCurrent(preview, previewKey, optionsKey);
}

/** A chart chosen through another backend must not be used for appending. */
export function quickHzChartIsCurrent(
  chart: string,
  chartApi: object | null,
  currentApi: object,
): boolean {
  return chart.length > 0 && chartApi === currentApi;
}
