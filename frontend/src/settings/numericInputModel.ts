export function commitNumericText(text: string, fallback: number, min: number, max: number) {
  const parsed = Number(text);
  if (text.trim() === "" || !Number.isFinite(parsed)) return fallback;
  return Math.max(min, Math.min(max, parsed));
}

/** Match Python round() (ties to even) used by the settings API. */
function roundToNearestEven(value: number): number {
  const lower = Math.floor(value);
  const fraction = value - lower;
  if (fraction < 0.5) return lower;
  if (fraction > 0.5) return lower + 1;
  return lower % 2 === 0 ? lower : lower + 1;
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
  // Merely focusing an existing fractional value must not rewrite it.
  if (next === fallback) return fallback;
  // HTML step=1 fields must use the same rounding as Python's _int_clamp.
  return integerStep ? roundToNearestEven(next) : next;
}
