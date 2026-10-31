/** Keep the same selection object when a state refresh did not remove notes. */
export function retainValidSelection(selection: number[], noteCount: number): number[] {
  const isValid = (index: number) => index >= 0 && index < noteCount;
  return selection.every(isValid) ? selection : selection.filter(isValid);
}
