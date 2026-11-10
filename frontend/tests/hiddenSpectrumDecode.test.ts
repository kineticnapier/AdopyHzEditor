import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const canvasSource = readFileSync(new URL("../src/editor/EditorCanvas.tsx", import.meta.url), "utf8");

test("Notes-only view does not decode the cached CQT payload", () => {
  assert.match(
    canvasSource,
    /const decoded = useMemo\(\(\) => props\.view\.mode === "notes" \? null : decodeSpectrum\(props\.spectrum\), \[props\.spectrum, props\.view\.mode\]\)/,
  );
});

test("Notes-only view skips Direct Spectrum unpacking and rebuilds when the mode changes", () => {
  const start = canvasSource.indexOf("  const directSpectrumCanvas = useMemo(() => {");
  const end = canvasSource.indexOf("  useEffect(() => {", start);
  assert.ok(start >= 0 && end > start, "missing Direct Spectrum memo");
  const memo = canvasSource.slice(start, end);
  const hiddenGuard = memo.indexOf('if (props.view.mode === "notes") return null;');
  const unpack = memo.indexOf("decodePackedDirectSpectrumBytes(");
  assert.ok(hiddenGuard >= 0 && unpack > hiddenGuard, "hidden Direct Spectrum must not be unpacked");
  assert.match(memo, /\},\[props\.directSpectrum,props\.settings\.colormap,props\.view\.mode\]\)/);
});
