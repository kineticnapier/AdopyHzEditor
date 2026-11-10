import type { PlaybackState } from "./bridge";

/** Explain why playback is unavailable instead of silently ignoring Play. */
export function playbackStatusMessage(
  playback: Pick<PlaybackState, "available" | "error">,
  hasPlayableContent = true,
): string | null {
  const error = playback.error?.trim();
  if (error) return `再生エラー: ${error}`;
  return playback.available || !hasPlayableContent ? null : "再生できません";
}

/** Disable no-op Play, but keep Pause available for an already playing stream. */
export function playbackToggleEnabled(
  connected: boolean,
  playback: Pick<PlaybackState, "available" | "playing">,
): boolean {
  return connected && (playback.available || playback.playing);
}
