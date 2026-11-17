import type { AdoFAIExportOptions } from "../api/bridge";

type CompressionMode = AdoFAIExportOptions["angleCompressionMode"];
type XMode = AdoFAIExportOptions["xMode"];

/** Fixed compression angles override the target-BPM X calculation in Python. */
export function xModeForCompression(mode: CompressionMode, xMode: XMode): XMode {
  return mode === "fixed" && xMode === "target_bpm" ? "floor" : xMode;
}

export function isXModeAvailable(mode: CompressionMode, xMode: XMode): boolean {
  return !(mode === "fixed" && xMode === "target_bpm");
}
