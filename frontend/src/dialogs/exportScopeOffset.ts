/** The displayed manual offset must match the chosen export range. */
export function exportScopeOffset(fullOffsetMs: number, selectedOffsetMs: number, selectedOnly: boolean): number {
  return selectedOnly ? selectedOffsetMs : fullOffsetMs;
}
