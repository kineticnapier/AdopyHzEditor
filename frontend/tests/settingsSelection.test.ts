import assert from "node:assert/strict";
import test from "node:test";
import { readFileSync } from "node:fs";
import { selectionIdentityKey } from "../src/settings/selectionIdentity.ts";

test("switching notes with the same selection count changes inspector identity", () => {
  assert.notEqual(selectionIdentityKey([3], []), selectionIdentityKey([7], []));
  assert.notEqual(selectionIdentityKey([3, 5], []), selectionIdentityKey([3, 6], []));
});

test("switching tracks with the same selection count changes inspector identity", () => {
  assert.notEqual(selectionIdentityKey([], [10]), selectionIdentityKey([], [11]));
  assert.notEqual(selectionIdentityKey([2], [10]), selectionIdentityKey([2], [11]));
});

test("identical selections retain a stable inspector identity across new arrays", () => {
  assert.equal(selectionIdentityKey([3, 5], [10]), selectionIdentityKey([3, 5], [10]));
  assert.notEqual(selectionIdentityKey([], []), selectionIdentityKey([0], []));
});

test("SettingsPanel reacts to selection identity instead of just selection lengths", () => {
  const source = readFileSync(new URL("../src/settings/SettingsPanel.tsx", import.meta.url), "utf8")
    .replace(/\r\n/g, "\n");
  assert.match(source, /const selectionKey = selectionIdentityKey\(selected, trackSelection\.ids\);/);
  assert.match(source, /useEffect\(\(\) => \{\s*if \(selected\.length \|\| trackSelection\.ids\.length\) setPage\("inspector"\);\s*\}, \[selectionKey\]\);/);
});
