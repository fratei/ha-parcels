import assert from "node:assert/strict";
import { describe, test } from "node:test";

import {
  SHOW_REVIEW_EVENT,
  aiQueueText,
  filteredTitle,
  hideHandled,
  hidePending,
  isHidden,
  reviewCount,
  senderCheckRows,
  settleHidden,
  showReview,
  trustResultText,
  unhide,
  unreadEmailsText,
  unreadRetryText,
  withoutHidden,
  type HiddenItems,
} from "../src/review-state.ts";
import type { MergeSuggestion, ReviewItem } from "../src/types.ts";

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

describe("trusting a sender", () => {
  test("says what happened to the sender's e-mails", () => {
    assert.equal(
      trustResultText({ domain: "shop.example", added: 1, rechecking: 2, kept: 1 }),
      "Trusted shop.example: added 1 e-mail, reading 2 e-mails again, 1 still needs review.",
    );
    assert.equal(
      trustResultText({ domain: "shop.example", added: 3, rechecking: 1, kept: 2 }),
      "Trusted shop.example: added 3 e-mails, reading 1 e-mail again, 2 still need review.",
    );
    assert.equal(
      trustResultText({ domain: "shop.example", added: 0, rechecking: 1, kept: 0 }),
      "Trusted shop.example: reading 1 e-mail again.",
    );
    assert.equal(
      trustResultText({ domain: "shop.example", added: 0, rechecking: 0, kept: 0 }),
      "Trusted shop.example.",
    );
  });
});

describe("sender check details", () => {
  const NO_RESULTS = { dkim: "", dmarc: "", spf: "" };

  test("lists the headers and the servers that wrote them, in order", () => {
    assert.deepEqual(
      senderCheckRows({
        headers: 2,
        servers: ["mx.example.net", ""],
        used: null,
        originals: 1,
        ...NO_RESULTS,
      }),
      [
        ["Authentication headers", "2"],
        ["Servers, in order", "mx.example.net, (no name)"],
        ["Renamed by the mail provider", "1"],
        ["Header used", "None"],
      ],
    );
  });

  test("shows the results of the header used", () => {
    assert.deepEqual(
      senderCheckRows({
        headers: 1,
        servers: ["mx.provider.example"],
        used: 0,
        dkim: "pass",
        dmarc: "fail",
        spf: "",
        originals: 0,
      }),
      [
        ["Authentication headers", "1"],
        ["Servers, in order", "mx.provider.example"],
        ["Header used", "Header 1"],
        ["DKIM", "pass"],
        ["DMARC", "fail"],
        ["SPF", "none"],
      ],
    );
  });

  test("an e-mail without headers", () => {
    assert.deepEqual(
      senderCheckRows({ headers: 0, servers: [], used: null, originals: 0, ...NO_RESULTS }),
      [
        ["Authentication headers", "0"],
        ["Header used", "None"],
      ],
    );
  });
});

describe("filteredTitle", () => {
  test("an e-mail filtered when it was read shows its subject", () => {
    assert.equal(filteredTitle({ subject: "  Your weekly offers  ", removed: false }), "Your weekly offers");
  });

  test("an e-mail without a subject says so", () => {
    assert.equal(filteredTitle({ subject: " ", removed: false }), "(no subject)");
  });

  test("an e-mail removed from a parcel says where it came from, as no subject is kept", () => {
    assert.equal(filteredTitle({ subject: "", removed: true }), "Removed from a parcel");
  });
});

describe("e-mails Parcels couldn't read", () => {
  const unread = (count: number, senders: string[], unnamed = 0) => ({
    count,
    senders,
    unnamed,
    newest: null,
  });

  test("say nothing when every e-mail was read", () => {
    assert.equal(unreadEmailsText(unread(0, ["a.example"])), null);
  });

  test("count the e-mails and name up to three senders", () => {
    assert.equal(unreadEmailsText(unread(1, [])), "Couldn't read 1 e-mail.");
    assert.equal(unreadEmailsText(unread(1, ["a.example"])), "Couldn't read 1 e-mail, from a.example.");
    assert.equal(
      unreadEmailsText(unread(4, ["a.example", "b.example"])),
      "Couldn't read 4 e-mails, from a.example and b.example.",
    );
    assert.equal(
      unreadEmailsText(unread(3, ["ups.com", "a.example", "b.example"])),
      "Couldn't read 3 e-mails, from ups.com, a.example and b.example.",
    );
    assert.equal(
      unreadEmailsText(unread(6, ["ups.com", "a.example", "b.example", "c.example", "d.example"])),
      "Couldn't read 6 e-mails, from ups.com, a.example, b.example and others.",
    );
  });

  test("say when a sender isn't known", () => {
    assert.equal(unreadEmailsText(unread(1, [], 1)), "Couldn't read 1 e-mail.");
    assert.equal(unreadEmailsText(unread(3, [], 3)), "Couldn't read 3 e-mails.");
    assert.equal(
      unreadEmailsText(unread(2, ["ups.com"], 1)),
      "Couldn't read 2 e-mails, from ups.com and an unknown sender.",
    );
    assert.equal(
      unreadEmailsText(unread(4, ["ups.com", "a.example"], 2)),
      "Couldn't read 4 e-mails, from ups.com, a.example and unknown senders.",
    );
    assert.equal(
      unreadEmailsText(unread(6, ["ups.com", "a.example", "b.example", "c.example"], 1)),
      "Couldn't read 6 e-mails, from ups.com, a.example, b.example and others.",
    );
  });

  test("say what trying again did", () => {
    assert.equal(
      unreadRetryText({ read: 1, failed: 1, gone: 1 }),
      "Tried again: read 1 e-mail, 1 still couldn't be read, 1 is no longer in the mailbox.",
    );
    assert.equal(unreadRetryText({ read: 2, failed: 0, gone: 0 }), "Tried again: read 2 e-mails.");
    assert.equal(
      unreadRetryText({ read: 0, failed: 3, gone: 2 }),
      "Tried again: 3 still couldn't be read, 2 are no longer in the mailbox.",
    );
    assert.equal(unreadRetryText({ read: 0, failed: 0, gone: 0 }), "No e-mails were waiting to be read again.");
  });
});

describe("the week card's link to Needs review", () => {
  test("counts what the review tab lists, the unread e-mails as one item", () => {
    const review = [{ id: "r1" }, { id: "r2" }] as ReviewItem[];
    const merge_suggestions = [{ id: "m1" }] as MergeSuggestion[];
    const unread = (count: number) => ({ count, senders: [], unnamed: 0, newest: null });
    assert.equal(reviewCount({ review, merge_suggestions, unread_emails: unread(3) }), 4);
    assert.equal(reviewCount({ review, merge_suggestions, unread_emails: unread(0) }), 3);
    assert.equal(reviewCount({ review: [], merge_suggestions: [], unread_emails: unread(0) }), 0);
  });

  test("reports whether a review card on the page took the request", () => {
    const page = new EventTarget();
    assert.equal(showReview(page), false);
    let seen: Event | null = null;
    page.addEventListener(SHOW_REVIEW_EVENT, (event) => {
      seen = event;
      event.preventDefault();
    });
    assert.equal(showReview(page), true);
    assert.equal((seen as Event | null)?.cancelable, true);
    assert.equal(showReview(null), false);
  });
});
