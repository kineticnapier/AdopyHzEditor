import type { NoteMutationResult } from "./bridge";

/** The backend may return one index or several after a preset insertion. */
export function presetInsertSelection(
  result: Pick<NoteMutationResult, "index" | "indices">,
): number[] {
  return result.indices ?? (result.index === undefined ? [] : [result.index]);
}
