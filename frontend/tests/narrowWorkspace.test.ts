import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { fileURLToPath } from "node:url";

const css = readFileSync(
  fileURLToPath(new URL("../src/styles.css", import.meta.url)),
  "utf8",
);

test("narrow workspace scrolls instead of crushing the editor canvas", () => {
  assert.match(
    css,
    /\.workspace\s*\{[^}]*grid-template-columns:\s*minmax\(480px,\s*1fr\)\s+286px;[^}]*overflow-x:\s*auto;[^}]*overflow-y:\s*hidden;/s,
  );
  assert.match(
    css,
    /@media\s*\(max-width:\s*920px\)[\s\S]*?\.workspace\s*\{[^}]*grid-template-columns:\s*minmax\(480px,\s*1fr\)\s+250px;/,
  );
});

test("collapsed inspector still keeps a usable editor width", () => {
  assert.match(
    css,
    /\.workspace\.panel-collapsed\s*\{[^}]*grid-template-columns:\s*minmax\(480px,1fr\)/,
  );
});

test("expanded settings sections retain their height and the sidebar remains scrollable", () => {
  const bodyRule = css.match(/\\.settings-body\\s*\\{([^}]*)\\}/)?.[1];
  assert.ok(bodyRule, "settings-body layout rule should exist");
  assert.match(bodyRule, /min-height:\\s*0;/);
  assert.match(bodyRule, /grid-auto-rows:\\s*max-content;/);
  assert.match(bodyRule, /overflow:\\s*auto;/);
  assert.match(bodyRule, /overscroll-behavior:\\s*contain;/);
});
