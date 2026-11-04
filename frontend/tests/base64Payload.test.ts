import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { decodeBase64Bytes, decodeSizedBase64Bytes } from "../src/editor/base64Payload.ts";

test("valid binary payloads preserve every byte", () => {
  assert.deepEqual(Array.from(decodeBase64Bytes("AAECA/8=") ?? []), [0, 1, 2, 3, 255]);
  assert.deepEqual(Array.from(decodeSizedBase64Bytes("AAECA/8=", 5) ?? []), [0, 1, 2, 3, 255]);
});

test("malformed base64 returns null instead of crashing canvas render", () => {
  for (const data of ["%%%", "☃", "a", "A==="]) {
    assert.equal(decodeBase64Bytes(data), null, data);
    assert.equal(decodeSizedBase64Bytes(data, 5), null, data);
  }
});

test("spectrum buffers must match their declared pixel count", () => {
  assert.equal(decodeSizedBase64Bytes("AQID", 2), null);
  assert.equal(decodeSizedBase64Bytes("AQID", 4), null);
  for (const invalidSize of [0, -1, 1.5, Number.NaN, Number.POSITIVE_INFINITY, Number.MAX_SAFE_INTEGER + 1])
    assert.equal(decodeSizedBase64Bytes("AQID", invalidSize), null);
  assert.deepEqual(Array.from(decodeSizedBase64Bytes("AQID", 3) ?? []), [1, 2, 3]);
});

test("all three canvas spectrum decoders use safe base64 conversion", () => {
  const source = readFileSync(new URL("../src/editor/EditorCanvas.tsx", import.meta.url), "utf8");
  assert.match(source, /decodeSizedBase64Bytes\(payload\.data, payload\.rows \* payload\.cols\)/);
  assert.match(source, /function decodeFrequencyTracks[\s\S]*?decodeBase64Bytes\(payload\.data\)/);
  assert.match(source, /const directSpectrumCanvas[\s\S]*?decodeBase64Bytes\(payload\.data\)/);
  assert.doesNotMatch(source, /\batob\(/);
});
