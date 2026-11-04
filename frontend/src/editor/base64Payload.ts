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
