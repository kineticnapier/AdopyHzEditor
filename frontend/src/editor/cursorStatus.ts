import type { CursorPeakPayload } from "../api/bridge";

function signedCents(value: number) {
  return `${value >= 0 ? "+" : ""}${value.toFixed(1)}c`;
}

export function formatCursorPeakLabel(peak: CursorPeakPayload): string | null {
  if (!peak.available) return null;
  if (peak.peakAvailable === false) return "CQT解析音域外（近傍ピークなし）";
  if (
    peak.peakName === undefined || peak.peakCents === undefined ||
    peak.peakHz === undefined || peak.peakDb === undefined
  ) return "近傍ピークなし";
  return `近傍 ${peak.peakName}${signedCents(peak.peakCents)} · ${peak.peakHz.toFixed(2)} Hz · ${peak.peakDb.toFixed(1)} dB`;
}
