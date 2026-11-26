import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { changedNewProject, effectiveNewProject, updateCheckMessage } from "../src/dialogs/preferencesModel.ts";

const builtin = {
  bpm: 175, gridEnabled: false, snapEnabled: false, snapDiv: 1,
  exportOctave: 0, previewSound: "sine", previewVolume: 20, colormap: "magma",
};

test("saved new-project values sit over the built-in ones", () => {
  const values = effectiveNewProject({ newProject: { bpm: 200 }, newProjectBuiltin: builtin });
  assert.equal(values.bpm, 200);
  assert.equal(values.colormap, "magma");
});

test("only values that differ from the built-in defaults are saved", () => {
  assert.deepEqual(changedNewProject({ ...builtin, bpm: 200, exportOctave: 1 }, builtin), { bpm: 200, exportOctave: 1 });
  assert.deepEqual(changedNewProject({ ...builtin }, builtin), {});
});

test("update check results read as one line", () => {
  assert.match(updateCheckMessage({ ok: true, current: "1.0.0", latest: "1.1.0", newer: true, url: "" }), /新しいバージョン 1\.1\.0/);
  assert.match(updateCheckMessage({ ok: true, current: "1.0.0", latest: "1.0.0", newer: false, url: "" }), /最新/);
  assert.match(updateCheckMessage({ ok: false, current: "1.0.0", url: "", error: "offline" }), /offline/);
});

test("the options menu opens 環境設定 and startup applies it", () => {
  const menus = readFileSync(new URL("../src/components/AppMenus.tsx", import.meta.url), "utf8");
  assert.match(menus, /onClick=\{p\.onPreferences\}>環境設定…/);
  const app = readFileSync(new URL("../src/App.tsx", import.meta.url), "utf8");
  assert.match(app, /void applyStartupPreferences\(backend as ToolBackendApi, \(\) => active\)/);
  assert.match(app, /update\.ok && update\.newer\) setToolDialog\("update"\)/);
  const exportDialog = readFileSync(new URL("../src/dialogs/AdoFAIExportDialogJa.tsx", import.meta.url), "utf8");
  assert.match(exportDialog, /api\.save_adofai_export_defaults\(snapshot\)/);
});
