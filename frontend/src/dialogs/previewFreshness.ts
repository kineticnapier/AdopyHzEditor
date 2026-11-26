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
