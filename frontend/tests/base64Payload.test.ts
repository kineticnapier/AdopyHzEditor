import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { decodeBase64Bytes, decodeSizedBase64Bytes, isValidDirectSpectrumSize } from "../src/editor/base64Payload.ts";

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


test("Direct Spectrum canvas dimensions respect the backend viewport limits", () => {
  for (const [width, height] of [[1, 1], [100, 128], [4096, 15], [1, 2048]])
    assert.equal(isValidDirectSpectrumSize(width, height), true, `${width}x${height}`);
  for (const [width, height] of [[0, 10], [-1, 10], [1.5, 10], [NaN, 10],
    [Infinity, 10], [4097, 1], [1, 2049], [4096, 2048], [65_001, 1]])
    assert.equal(isValidDirectSpectrumSize(width, height), false, `${width}x${height}`);
});

test("canvas rejects invalid Direct Spectrum dimensions before allocation", () => {
  const source = readFileSync(new URL("../src/editor/EditorCanvas.tsx", import.meta.url), "utf8");
  const section = source.slice(source.indexOf("const directSpectrumCanvas = useMemo"));
  assert.match(section, /isValidDirectSpectrumSize\(payload\.timeBuckets, payload\.pitchBuckets\)/);
  assert.ok(section.indexOf("isValidDirectSpectrumSize(") < section.indexOf('document.createElement("canvas")'));
  assert.ok(section.indexOf("decodeBase64Bytes(payload.data)") < section.indexOf('document.createElement("canvas")'));
});

test("frequency track decoder validates record count before allocating typed arrays", () => {
  const source = readFileSync(new URL("../src/editor/EditorCanvas.tsx", import.meta.url), "utf8");
  const section = source.slice(source.indexOf("function decodeFrequencyTracks"), source.indexOf("function snapTime"));
  assert.match(section, /Number\.isSafeInteger\(payload\.pointCount\)/);
  assert.match(section, /payload\.pointCount <= 0/);
  assert.ok(section.indexOf("Number.isSafeInteger(payload.pointCount)") < section.indexOf("new Uint32Array(count)"));
});
