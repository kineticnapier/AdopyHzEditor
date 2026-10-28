/** Show the start hint only before either audio or editable notes exist. */
export function shouldShowCanvasEmptyHint(
  audioName: string | null,
  noteCount: number,
): boolean {
  return audioName === null && noteCount === 0;
}
