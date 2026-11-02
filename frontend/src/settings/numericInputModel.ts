export function commitNumericText(text: string, fallback: number, min: number, max: number) {
  const parsed = Number(text);
  if (text.trim() === "" || !Number.isFinite(parsed)) return fallback;
  return Math.max(min, Math.min(max, parsed));
}

/** Escape must win over blur even when React has not flushed setText. */
export function commitNumericEdit(
  text: string,
  fallback: number,
  min: number,
  max: number,
  cancelled: boolean,
  integerStep = false,
) {
  if (cancelled || text.trim() === "" || !Number.isFinite(Number(text))) return fallback;
  const next = commitNumericText(text, fallback, min, max);
  // HTML step=1 fields must not send fractional values to integer APIs.
  return integerStep ? Math.round(next) : next;
}
