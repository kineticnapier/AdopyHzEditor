/** Decode untrusted backend base64 without throwing during React render. */
export function decodeBase64Bytes(data: string): Uint8Array | null {
  try {
    const raw = atob(data);
    return Uint8Array.from(raw, (char) => char.charCodeAt(0));
  } catch {
    return null;
  }
}

/** Reject truncated or oversized image buffers before indexing their pixels. */
export function decodeSizedBase64Bytes(data: string, expectedLength: number): Uint8Array | null {
  if (!Number.isSafeInteger(expectedLength) || expectedLength <= 0) return null;
  const bytes = decodeBase64Bytes(data);
  return bytes && bytes.byteLength === expectedLength ? bytes : null;
}

/** Backend viewport queries cap Direct Spectrum at 4096x2048 and 65,000 cells.
 * Validate untrusted dimensions before creating a canvas during React render. */
export function isValidDirectSpectrumSize(width: number, height: number): boolean {
  return Number.isSafeInteger(width) && width > 0 && width <= 4096 &&
    Number.isSafeInteger(height) && height > 0 && height <= 2048 &&
    width * height <= 65_000;
}

/** Reject incomplete or inconsistent packed frequency-track responses.
 * The backend emits exactly 18 bytes per point, capped at 30,000 points. */
export function decodePackedFrequencyTrackBytes(data: string, pointCount: number): Uint8Array | null {
  if (!Number.isSafeInteger(pointCount) || pointCount <= 0 || pointCount > 30_000) return null;
  return decodeSizedBase64Bytes(data, pointCount * 18);
}

/** Reject truncated, oversized or inconsistent packed Direct Spectrum cells.
 * Each occupied cell has a 2-byte time, 2-byte pitch and 1-byte magnitude. */
export function decodePackedDirectSpectrumBytes(data: string, recordCount: number, width: number, height: number): Uint8Array | null {
  if (!isValidDirectSpectrumSize(width, height) ||
      !Number.isSafeInteger(recordCount) || recordCount <= 0 || recordCount > width * height) return null;
  return decodeSizedBase64Bytes(data, recordCount * 5);
}
