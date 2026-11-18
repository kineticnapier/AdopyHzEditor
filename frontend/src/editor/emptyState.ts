/** Show the start hint only before either audio or editable notes exist. */
export function shouldShowCanvasEmptyHint(
  audioName: string | null,
  noteCount: number,
): boolean {
  return audioName === null && noteCount === 0;
}

/** Distinguish notes-only editing from a genuinely empty workspace in the title bar. */
export function workspaceTitle(audioName: string | null, hasPlayableContent: boolean): string {
  if (audioName !== null) return audioName;
  return hasPlayableContent ? "ノートのみのワークスペース" : "空のワークスペース";
}
