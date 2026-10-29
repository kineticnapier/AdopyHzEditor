import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

test("documented Note Preset compatibility API does not introduce a Web UI tab", () => {
  const product = readFileSync(new URL("../../PRODUCT.md", import.meta.url), "utf8");
  const settings = readFileSync(new URL("../src/settings/SettingsPanel.tsx", import.meta.url), "utf8");
  const app = readFileSync(new URL("../src/App.tsx", import.meta.url), "utf8");
  assert.match(product, /Note Preset UI, and a dedicated Quantize button are intentionally absent/);
  assert.doesNotMatch(settings, /NotePresetPanel|setPage\(["']presets["']\)/);
  assert.doesNotMatch(app, /queuePresetAction|onQueuedPresetAction/);
});
