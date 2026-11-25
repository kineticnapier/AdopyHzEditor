import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { KPS_LISTED_RANGES, kpsRangeLines } from "../src/dialogs/exportResult.ts";

const range = (floor: number) => ({ startFloor: floor, endFloor: floor + 9, startSeconds: floor / 100, maxKps: 232.6 });

test("each too-fast stretch is listed by tile number", () => {
  const lines = kpsRangeLines({ limit: 200, maxKps: 232.6, tilesOver: 10, ranges: [range(3334)] });
  assert.deepEqual(lines, ["タイル 3334〜3343（譜面の 33.34秒〜）最大 233 KPS"]);
  const single = kpsRangeLines({ limit: 200, maxKps: 250, tilesOver: 1, ranges: [{ ...range(12), endFloor: 12 }] });
  assert.match(single[0], /^タイル 12（/);
});

test("a long list is cut short with a count of the rest", () => {
  const ranges = Array.from({ length: KPS_LISTED_RANGES + 3 }, (_v, i) => range(i * 20));
  const lines = kpsRangeLines({ limit: 200, maxKps: 232.6, tilesOver: 99, ranges });
  assert.equal(lines.length, KPS_LISTED_RANGES + 1);
  assert.equal(lines.at(-1), "ほか 3 か所");
  assert.deepEqual(kpsRangeLines(null), []);
});

test("the export dialog stays open to show the KPS warning", () => {
  const source = readFileSync(new URL("../src/dialogs/AdoFAIExportDialogJa.tsx", import.meta.url), "utf8");
  assert.match(source, /r\.ok && r\.kps && r\.kps\.ranges\.length/);
  assert.match(source, /setKpsNotice\(/);
  assert.match(source, /kpsRangeLines\(kpsNotice\.report\)/);
});
