import { t } from "../i18n/index.ts";
import type { CursorPeakPayload } from "../api/bridge";

function signedCents(value: number) {
  return `${value >= 0 ? "+" : ""}${value.toFixed(1)}c`;
}

export function formatCursorPeakLabel(peak: CursorPeakPayload): string | null {
  if (!peak.available) return null;
  if (peak.peakAvailable === false) return t("cursor.out_of_range");
  if (
    peak.peakName === undefined || peak.peakCents === undefined ||
    peak.peakHz === undefined || peak.peakDb === undefined
  ) return t("cursor.no_peak");
  return `${t("cursor.peak", { name: `${peak.peakName}${signedCents(peak.peakCents)}` })} · ${peak.peakHz.toFixed(2)} Hz · ${peak.peakDb.toFixed(1)} dB`;
}
