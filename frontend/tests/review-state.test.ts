import assert from "node:assert/strict";
import { describe, test } from "node:test";

import {
  aiQueueText,
  hideHandled,
  hidePending,
  isHidden,
  settleHidden,
  unhide,
  withoutHidden,
  type HiddenItems,
} from "../src/review-state.ts";

interface FakeSnapshot {
  readonly name: string;
}

const BEFORE: FakeSnapshot = { name: "before" };
const AFTER: FakeSnapshot = { name: "after" };
const ITEMS = [{ id: "a" }, { id: "b" }, { id: "c" }];
const NONE: HiddenItems<FakeSnapshot> = new Map();

describe("optimistic review items", () => {
  test("hide an item at once, whichever snapshot is current", () => {
    const hidden = hidePending(NONE, ["b"]);
    assert.deepEqual(withoutHidden(ITEMS, hidden, BEFORE), [{ id: "a" }, { id: "c" }]);
    assert.deepEqual(withoutHidden(ITEMS, hidden, AFTER), [{ id: "a" }, { id: "c" }]);
    assert.equal(withoutHidden(ITEMS, NONE, BEFORE), ITEMS);
    assert.equal(withoutHidden(ITEMS, hidePending(NONE, ["x"]), BEFORE), ITEMS);
  });

  test("a handled item stays hidden until the next snapshot", () => {
    const listed = (itemId: string): boolean => ITEMS.some((item) => item.id === itemId);
    const hidden = hideHandled(hidePending(NONE, ["b"]), ["b"], BEFORE, listed);
    assert.equal(isHidden(hidden, "b", BEFORE), true);
    assert.equal(settleHidden(hidden, BEFORE), hidden);
    // The next snapshot shows the server's lists, so the item is no longer hidden.
    assert.equal(isHidden(hidden, "b", AFTER), false);
    assert.equal(settleHidden(hidden, AFTER).size, 0);
  });

  test("an item the snapshot already dropped isn't kept", () => {
    const hidden = hideHandled(hidePending(NONE, ["b"]), ["b"], AFTER, () => false);
    assert.equal(hidden.size, 0);
    assert.equal(hideHandled(hidePending(NONE, ["b"]), ["b"], null, () => true).size, 0);
  });

  test("a running command keeps its item hidden over new snapshots", () => {
    const hidden = hidePending(NONE, ["a", "c"]);
    assert.equal(settleHidden(hidden, AFTER), hidden);
    assert.deepEqual(withoutHidden(ITEMS, hidden, AFTER), [{ id: "b" }]);
    // A failed command shows its items again.
    assert.equal(unhide(hidden, ["a", "c"]).size, 0);
    assert.deepEqual(withoutHidden(ITEMS, unhide(hidden, ["a"]), AFTER), [{ id: "a" }, { id: "b" }]);
  });
});

describe("local AI line", () => {
  test("shows nothing while the queue is empty", () => {
    assert.equal(aiQueueText(0, 120), null);
  });

  test("counts the e-mails and estimates the wait", () => {
    assert.equal(aiQueueText(1, null), "1 e-mail waiting for the local AI");
    assert.equal(aiQueueText(3, null), "3 e-mails waiting for the local AI");
    assert.equal(aiQueueText(3, 159), "3 e-mails waiting for the local AI, about 3 min");
    assert.equal(aiQueueText(1, 7), "1 e-mail waiting for the local AI, about 1 min");
    assert.equal(aiQueueText(60, 7140), "60 e-mails waiting for the local AI, about 119 min");
    assert.equal(aiQueueText(70, 7200), "70 e-mails waiting for the local AI, about 2 h");
    assert.equal(aiQueueText(90, 9000), "90 e-mails waiting for the local AI, about 3 h");
  });
});
