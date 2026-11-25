/** A backend may report a failed export as a resolved result, not an exception. */
export function exportFailureMessage(result: { ok: boolean; status: string }): string | null {
  if (result.ok) return null;
  const status = result.status.trim();
  // Closing the native Save dialog is not an export error.
  if (status.toLowerCase() === "cancelled" || status === "キャンセルしました") return null;
  return status || "ADOFAIの書き出しに失敗しました";
}

import type { AdoFAIKpsRange, AdoFAIKpsReport } from "../api/bridge";

/** Ranges listed in the export dialog; the rest are counted. */
export const KPS_LISTED_RANGES = 10;

/** One line per too-fast stretch, as floor numbers to find in the ADOFAI editor. */
export function kpsRangeLines(report: AdoFAIKpsReport | null | undefined): string[] {
  const ranges: AdoFAIKpsRange[] = report?.ranges ?? [];
  const lines = ranges.slice(0, KPS_LISTED_RANGES).map((r) => {
    const floors = r.startFloor === r.endFloor ? `${r.startFloor}` : `${r.startFloor}〜${r.endFloor}`;
    return `タイル ${floors}（譜面の ${r.startSeconds.toFixed(2)}秒〜）最大 ${Math.round(r.maxKps)} KPS`;
  });
  if (ranges.length > KPS_LISTED_RANGES) lines.push(`ほか ${ranges.length - KPS_LISTED_RANGES} か所`);
  return lines;
}

/** A cancelled Save dialog must not overwrite the editor's current status. */
export function exportStatusMessage(result: { ok: boolean; status: string }): string | null {
  return result.ok ? result.status : exportFailureMessage(result);
}
