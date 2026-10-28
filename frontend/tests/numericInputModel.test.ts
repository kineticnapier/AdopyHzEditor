import assert from "node:assert/strict";
import test from "node:test";
import { commitNumericText, commitNumericEdit } from "../src/settings/numericInputModel.ts";

test("transient numeric strings keep the prior committed value", () => {
  assert.equal(commitNumericText("", 12.5, 0, 127), 12.5);
  assert.equal(commitNumericText("-", 12.5, 0, 127), 12.5);
  assert.equal(commitNumericText("1e", 12.5, 0, 127), 12.5);
});

test("committed numeric values retain fractions and clamp to bounds", () => {
  assert.equal(commitNumericText("60.25", 0, 0, 127), 60.25);
  assert.equal(commitNumericText("200", 0, 0, 127), 127);
});

test("Escape cancels the edit even when blur sees stale text", () => {
  assert.equal(commitNumericEdit("2.000", 1, 0, 36000, true), 1);
  assert.equal(commitNumericEdit("-4", 12, -600000, 600000, true), 12);
});

test("Enter and blur still commit valid values", () => {
  assert.equal(commitNumericEdit("2.000", 1, 0, 36000, false), 2);
  assert.equal(commitNumericEdit("-4", 12, -600000, 600000, false), -4);
  assert.equal(commitNumericEdit("200", 10, 0, 127, false), 127);
});
