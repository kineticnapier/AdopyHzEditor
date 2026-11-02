import assert from "node:assert/strict";
import test from "node:test";
import { readFileSync } from "node:fs";
import { isDialogCompositionKey } from "../src/dialogs/dialogFocus.ts";

test("timeline numeric inputs defer Enter and Escape during IME composition", () => {
  assert.equal(isDialogCompositionKey({ isComposing: true, keyCode: 13 }), true);
  assert.equal(isDialogCompositionKey({ isComposing: true, keyCode: 27 }), true);
  assert.equal(isDialogCompositionKey({ isComposing: false, keyCode: 229 }), true);
  assert.equal(isDialogCompositionKey({ isComposing: false, keyCode: 13 }), false);
});

test("timeline numeric field checks IME before Enter/Escape and contains keyboard events", () => {
  const source = readFileSync(new URL("../src/editor/Timeline.tsx", import.meta.url), "utf8")
    .replace(/\r\n/g, "\n");
  const start = source.indexOf("function CommitNumber(");
  assert.ok(start >= 0, "timeline numeric component exists");
  const field = source.slice(start);
  const composition = field.indexOf("if (isDialogCompositionKey(event.nativeEvent)) return;");
  const enter = field.indexOf('if (event.key === "Enter")');
  const escape = field.indexOf('else if (event.key === "Escape")');
  assert.ok(composition >= 0 && composition < enter && enter < escape,
    "IME check must run before numeric Enter/Escape handlers");
  assert.match(field.slice(enter, escape), /event\.preventDefault\(\);[\s\S]*event\.stopPropagation\(\);[\s\S]*event\.currentTarget\.blur\(\)/,
    "Enter commits without leaking into parent keyboard handlers");
  assert.match(field.slice(escape), /event\.preventDefault\(\);[\s\S]*event\.stopPropagation\(\);[\s\S]*cancelledRef\.current = true/,
    "Escape cancels without triggering parent shortcuts");
});
