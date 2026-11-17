/** Render a playback timestamp in minutes, seconds, and milliseconds.
 * Invalid or unrepresentable metadata is unknown, not zero seconds.
 */
export function formatPlaybackTime(seconds: number): string {
  if (!Number.isFinite(seconds)) return "--:--.---";
  const totalMs = Math.round(Math.max(0, seconds) * 1000);
  if (!Number.isSafeInteger(totalMs)) return "--:--.---";
  const minutes = Math.floor(totalMs / 60000);
  const sec = Math.floor((totalMs % 60000) / 1000);
  const ms = totalMs % 1000;
  return `${minutes}:${String(sec).padStart(2, "0")}.${String(ms).padStart(3, "0")}`;
}
