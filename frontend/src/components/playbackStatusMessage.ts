import type { PlaybackState } from "./bridge";

/** Explain why playback is unavailable instead of silently ignoring Play. */
export function playbackStatusMessage(
  playback: Pick<PlaybackState, "available" | "error">,
): string | null {
  const error = playback.error?.trim();
  if (error) return `再生エラー: ${error}`;
  return playback.available ? null : "再生できません";
}
