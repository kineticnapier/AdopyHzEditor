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

/** A successful insertion may change selection; only document/API replacement invalidates its completion. */
export function documentActionIsCurrent(
  started: { api: object; documentGeneration: number },
  current: { api: object; documentGeneration: number },
): boolean {
  return started.api === current.api &&
    started.documentGeneration === current.documentGeneration;
}

/** Reject a MIDI range that the Python blank-workspace API would silently rewrite. */
export function blankWorkspaceMidiRangeIsValid(
  value: { midiMin: number; midiMax: number } | null,
): boolean {
  return value !== null &&
    Number.isInteger(value.midiMin) &&
    Number.isInteger(value.midiMax) &&
    value.midiMin >= 0 &&
    value.midiMax <= 127 &&
    value.midiMin < value.midiMax;
}
