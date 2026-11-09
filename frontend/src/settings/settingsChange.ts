/** Avoid a false unsaved warning for settings patches that change nothing. */
export function hasEffectiveSettingsChange<T extends object>(
  current: T,
  changes: Partial<T>,
): boolean {
  return (Object.keys(changes) as (keyof T)[]).some(
    (key) => current[key] !== changes[key],
  );
}

/** Compare consecutive edits against the latest requested values, not a stale
 * React render. The ref is updated synchronously before the backend call. */
export function acceptSettingsPatch<T extends object>(
  snapshot: { current: T },
  changes: Partial<T>,
): boolean {
  if (!hasEffectiveSettingsChange(snapshot.current, changes)) return false;
  snapshot.current = { ...snapshot.current, ...changes };
  return true;
}
