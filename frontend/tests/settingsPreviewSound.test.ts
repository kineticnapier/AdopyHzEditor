import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { fileURLToPath } from "node:url";

const panel = readFileSync(
  fileURLToPath(new URL("../src/settings/SettingsPanel.tsx", import.meta.url)),
  "utf8",
);

test("ADOFAI kick is selectable from the note preview sound setting", () => {
  const previewSoundRow = panel.match(
    /<Row label="試聴音色">([\s\S]*?)<\/Row>/,
  )?.[1];
  assert.ok(previewSoundRow, "note preview sound selector must exist");
  assert.match(previewSoundRow, /value=\{settings\.previewSound\}/);
  assert.match(previewSoundRow, /\["adofai_kick",\s*"ADOFAI Kick"\]/);
  assert.match(previewSoundRow, /onPatch\(\{ previewSound: v \}\)/);
});
