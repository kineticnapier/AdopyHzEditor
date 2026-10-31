/** Failed or obsolete Track lookups must not clear the user's selection. */
export async function resolveTrackLookup(
  lookup: () => Promise<{ trackIds: number[]; status: string }>,
  isCurrent: () => boolean,
  report: (message: string) => void,
): Promise<number[] | null> {
  try {
    const result = await lookup();
    if (!isCurrent()) return null;
    report(result.status);
    return result.trackIds;
  } catch (error) {
    if (!isCurrent()) return null;
    report(String(error));
    return null;
  }
}
