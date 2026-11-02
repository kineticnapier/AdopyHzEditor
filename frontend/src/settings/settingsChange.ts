/** Avoid a false unsaved warning for settings patches that change nothing. */
export function hasEffectiveSettingsChange<T extends object>(
  current: T,
  changes: Partial<T>,
): boolean {
  return (Object.keys(changes) as (keyof T)[]).some(
    (key) => current[key] !== changes[key],
  );
}
