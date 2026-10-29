import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import test from "node:test";

test("note preset UI stays intentionally absent without removing compatibility APIs", () => {
  const panel = new URL("../src/settings/NotePresetPanel.tsx", import.meta.url);
  const readme = readFileSync(new URL("../README.md", import.meta.url), "utf8");
  const product = readFileSync(new URL("../../PRODUCT.md", import.meta.url), "utf8");
  const backend = readFileSync(new URL("../../web/presets.py", import.meta.url), "utf8");

  assert.equal(existsSync(panel), false);
  assert.match(readme, /単音プリセットUIは.*提供しません/);
  assert.match(product, /Note Preset UI.*intentionally absent/);
  assert.match(backend, /def get_note_presets\(/);
  assert.match(backend, /def save_note_preset\(/);
  assert.match(backend, /def insert_note_preset\(/);
});
