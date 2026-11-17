/** A response from an older settings request or document must not replace newer edits. */
export function settingsResponseIsCurrent(
  requestCurrent: boolean,
  pendingChanges: boolean,
  requestGeneration: number,
  currentGeneration: number,
): boolean {
  return requestCurrent && !pendingChanges && requestGeneration === currentGeneration;
}
