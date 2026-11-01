/** A selection change must be detected even when its item count stays the same. */
export function selectionIdentityKey(
  selectedNotes: readonly number[],
  selectedTracks: readonly number[],
): string {
  return JSON.stringify([selectedNotes, selectedTracks]);
}
