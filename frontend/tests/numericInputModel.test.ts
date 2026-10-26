import assert from "node:assert/strict";
import test from "node:test";
import { commitNumericText } from "../src/settings/numericInputModel.ts";

test("transient numeric strings keep the prior committed value", () => {
  assert.equal(commitNumericText("", 12.5, 0, 127), 12.5);
  assert.equal(commitNumericText("-", 12.5, 0, 127), 12.5);
  assert.equal(commitNumericText("1e", 12.5, 0, 127), 12.5);
});

test("committed numeric values retain fractions and clamp to bounds", () => {
  assert.equal(commitNumericText("60.25", 0, 0, 127), 60.25);
  assert.equal(commitNumericText("200", 0, 0, 127), 127);
});
