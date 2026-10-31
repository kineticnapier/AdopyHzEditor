import assert from "node:assert/strict";
import test from "node:test";
import { consumeMenuEscape } from "../src/components/menuEscape.ts";

function keyEvent(key: string) {
  let prevented = false;
  return {
    event: {
      key,
      get defaultPrevented() { return prevented; },
      preventDefault() { prevented = true; },
    },
    isPrevented: () => prevented,
  };
}

test("Escape closes an open menu and prevents the global Escape shortcut", () => {
  const { event, isPrevented } = keyEvent("Escape");
  const closed: string[] = [];
  assert.equal(consumeMenuEscape(event, "file", id => closed.push(id)), true);
  assert.equal(isPrevented(), true);
  assert.deepEqual(closed, ["file"]);
});

test("Escape with no open menu remains available to the editor", () => {
  const { event, isPrevented } = keyEvent("Escape");
  assert.equal(consumeMenuEscape(event, null, () => assert.fail("must not close")), false);
  assert.equal(isPrevented(), false);
});

test("other keys retain menu and editor keyboard behavior", () => {
  for (const key of ["ArrowLeft", "ArrowRight", "Tab", "Enter"]) {
    const { event, isPrevented } = keyEvent(key);
    assert.equal(consumeMenuEscape(event, "file", () => assert.fail("must not close")), false);
    assert.equal(isPrevented(), false);
  }
});

test("an already-handled Escape is not handled twice", () => {
  const { event } = keyEvent("Escape");
  event.preventDefault();
  assert.equal(consumeMenuEscape(event, "file", () => assert.fail("must not close")), false);
});
