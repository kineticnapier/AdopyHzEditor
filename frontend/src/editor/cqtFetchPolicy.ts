import type { ViewState } from "./bridge";

/** A hidden CQT layer needs no backend fetch, including during document load. */
export function shouldFetchCqtSpectrum(
  analysisAvailable: boolean,
  analysisSource: string | null | undefined,
  mode: ViewState["mode"],
): boolean {
  return analysisAvailable && analysisSource !== "vorbis_direct" && mode !== "notes";
}
