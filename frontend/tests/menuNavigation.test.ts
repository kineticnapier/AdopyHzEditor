import assert from "node:assert/strict";
import test from "node:test";
import { nextMenuId } from "../src/components/menuNavigation.ts";

const ids = ["file", "edit", "analyze", "tools", "options", "help"] as const;

test("arrow navigation uses the focused trigger rather than an older open menu", () => {
  assert.equal(nextMenuId(ids, "file", "edit", "ArrowRight"), "analyze");
  assert.equal(nextMenuId(ids, "file", "edit", "ArrowLeft"), "file");
});

test("arrow navigation from an open popup uses the active menu", () => {
  assert.equal(nextMenuId(ids, "analyze", null, "ArrowRight"), "tools");
  assert.equal(nextMenuId(ids, "analyze", null, "ArrowLeft"), "edit");
});

test("arrow navigation wraps and rejects an unknown trigger", () => {
  assert.equal(nextMenuId(ids, null, "help", "ArrowRight"), "file");
  assert.equal(nextMenuId(ids, null, "file", "ArrowLeft"), "help");
  assert.equal(nextMenuId(ids, null, "unknown", "ArrowRight"), null);
  assert.equal(nextMenuId(ids, null, null, "ArrowRight"), null);
});
