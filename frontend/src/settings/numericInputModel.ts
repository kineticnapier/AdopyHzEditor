export function commitNumericText(text: string, fallback: number, min: number, max: number) {
  const parsed = Number(text);
  if (text.trim() === "" || !Number.isFinite(parsed)) return fallback;
  return Math.max(min, Math.min(max, parsed));
}
