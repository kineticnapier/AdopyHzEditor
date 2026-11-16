/**
 * Prevents stacked destructive actions on the same notes.
 *
 * Cut and delete send note indices captured from the current render. While such
 * a request is queued or in flight, those indices may already refer to other
 * notes on the backend, so a further request touching any of them (key repeat,
 * double-activated menu item, Delete during Ctrl+X) is dropped instead of being
 * queued behind the first one.
 */
export function createSelectionMutationGuard() {
  const inFlight = new Map<number, number>();
  return {
    /** Resolves `false` when the action was skipped. */
    async run(indices: readonly number[], action: () => Promise<unknown>): Promise<boolean> {
      const unique = [...new Set(indices)];
      if (!unique.length || unique.some((i) => inFlight.has(i))) return false;
      for (const i of unique) inFlight.set(i, (inFlight.get(i) ?? 0) + 1);
      try {
        await action();
        return true;
      } finally {
        for (const i of unique) {
          const count = (inFlight.get(i) ?? 1) - 1;
          if (count > 0) inFlight.set(i, count);
          else inFlight.delete(i);
        }
      }
    },
  };
}
