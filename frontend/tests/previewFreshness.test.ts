import assert from "node:assert/strict";
import test from "node:test";
import { previewIsCurrent } from "../src/dialogs/previewFreshness.ts";

const original = JSON.stringify({ rootHz: 440, harmonics: "1,2,3" });
const changed = JSON.stringify({ rootHz: 442, harmonics: "1,2,3" });

test("current harmonic preview is visible and eligible for insertion", () => {
  assert.equal(previewIsCurrent({ rows: [1, 2, 3] }, original, original), true);
});

test("old harmonic preview is hidden immediately after options change", () => {
  assert.equal(previewIsCurrent({ rows: [1, 2, 3] }, original, changed), false);
});

test("missing preview cannot become current even when keys match", () => {
  assert.equal(previewIsCurrent(null, original, original), false);
});

test("returning to the exact original options permits the matching preview", () => {
  assert.equal(previewIsCurrent({ rows: [1] }, original, original), true);
  assert.equal(previewIsCurrent({ rows: [1] }, original, changed), false);
});
