/** Keep the same selection object when a state refresh did not remove notes.
 * Selection entries are array indices: a fractional or non-finite value must
 * never survive a refresh and reach a note edit or keyboard navigation.
 */
export function retainValidSelection(selection: number[], noteCount: number): number[] {
  const isValid = (index: number) => Number.isSafeInteger(index) && index >= 0 && index < noteCount;
  return selection.every(isValid) ? selection : selection.filter(isValid);
}
