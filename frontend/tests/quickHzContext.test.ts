import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { quickHzChartIsCurrent, quickHzPreviewIsCurrent } from "../src/dialogs/previewFreshness.ts";

test("Quick Hz preview is invalid immediately when the backend changes", () => {
  const oldApi = {};
  const newApi = {};
  const preview = { output: "generated" };
  assert.equal(quickHzPreviewIsCurrent(preview, "options", "options", oldApi, oldApi), true);
  assert.equal(quickHzPreviewIsCurrent(preview, "options", "options", oldApi, newApi), false);
  assert.equal(quickHzPreviewIsCurrent(preview, "options", "changed", oldApi, oldApi), false);
  assert.equal(quickHzPreviewIsCurrent(preview, "options", "options", null, oldApi), false);
});

test("Quick Hz chart selection is scoped to the backend that selected it", () => {
  const oldApi = {};
  const newApi = {};
  assert.equal(quickHzChartIsCurrent("chart.adofai", oldApi, oldApi), true);
  assert.equal(quickHzChartIsCurrent("chart.adofai", oldApi, newApi), false);
  assert.equal(quickHzChartIsCurrent("", oldApi, oldApi), false);
});

test("Quick Hz dialog blocks old picker, append, and output completions", () => {
  const source = readFileSync(new URL("../src/dialogs/ToolDialogs.tsx", import.meta.url), "utf8");
  const start = source.indexOf("export function QuickHzDialog(");
  const end = source.indexOf("export function HarmonicDiagramDialog(", start);
  assert.ok(start >= 0 && end > start);
  const dialog = source.slice(start, end);
  const picker = dialog.slice(dialog.indexOf("async function chooseChart()"), dialog.indexOf("async function append()"));
  const append = dialog.slice(dialog.indexOf("async function append()"), dialog.indexOf("async function copy()"));
  const outputs = dialog.slice(dialog.indexOf("async function copy()"), dialog.indexOf("  return (", dialog.indexOf("async function saveText()")));
  assert.match(dialog, /quickHzPreviewIsCurrent\(result, resultKey, optsKey, resultApi, api\)/);
  assert.match(dialog, /quickHzChartIsCurrent\(chart, chartApi, api\)/);
  assert.match(dialog, /quickHzActionPolicy\(busy, chartCurrent, resultCurrent\)/);
  assert.match(dialog, /setResultApi\(api\)/);
  assert.match(dialog, /setChartApi\(api\)/);
  assert.match(picker, /if \(api !== latestApi\.current\) return/);
  assert.match(append, /if \(api !== latestApi\.current\) return/);
  assert.match(outputs, /api === latestApi\.current/g);
  assert.match(dialog, /chartCurrent \? chart\.split/);
});
