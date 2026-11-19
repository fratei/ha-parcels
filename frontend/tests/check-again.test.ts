import assert from "node:assert/strict";
import { describe, test } from "node:test";

import { canCheckAgain, checkAgainText, normalizeCheckAgain } from "../src/check-again.ts";
import { makeParcel } from "./helpers.ts";

const AUTO = { enabled: true, mode: "auto" } as const;
const SUGGEST = { enabled: true, mode: "suggest" } as const;
const OFF = { enabled: false, mode: "off" } as const;

describe("Check again", () => {
  test("is offered to administrators on open parcels without a date", () => {
    const undated = makeParcel({ status: "shipped" });
    assert.equal(canCheckAgain(undated, true), true);
    assert.equal(canCheckAgain(undated, false), false);
    assert.equal(canCheckAgain({ ...undated, eta_start: "2026-11-20" }, true), false);
    assert.equal(canCheckAgain({ ...undated, eta_end: "2026-11-20" }, true), false);
    assert.equal(canCheckAgain({ ...undated, status: "delivered" }, true), false);
    assert.equal(canCheckAgain({ ...undated, status: "cancelled" }, true), false);
    assert.equal(canCheckAgain({ ...undated, archived: true }, true), false);
    assert.equal(canCheckAgain({ ...undated, restricted: true }, true), false);
  });

  test("says what it read and what the local AI does next", () => {
    assert.equal(
      checkAgainText({ read: 2, queued: 2, gone: 0, failed: 0 }, SUGGEST),
      "Read 2 e-mails again. The local AI is checking 2 e-mails. " +
        "What it finds waits under Needs review.",
    );
    assert.equal(
      checkAgainText({ read: 1, queued: 1, gone: 0, failed: 0 }, AUTO),
      "Read 1 e-mail again. The local AI is checking 1 e-mail. " +
        "What it finds is added to this parcel.",
    );
    assert.equal(
      checkAgainText({ read: 1, queued: 0, gone: 0, failed: 0 }, AUTO),
      "Read 1 e-mail again. There was nothing for the local AI to fill in.",
    );
    assert.equal(
      checkAgainText({ read: 3, queued: 0, gone: 0, failed: 0 }, OFF),
      "Read 3 e-mails again. The local AI is off.",
    );
  });

  test("says which e-mails it couldn't read", () => {
    assert.equal(
      checkAgainText({ read: 1, queued: 0, gone: 1, failed: 1 }, OFF),
      "Read 1 e-mail again. 1 e-mail is no longer in the mailbox. " +
        "1 e-mail couldn't be downloaded; try again later. The local AI is off.",
    );
    assert.equal(
      checkAgainText({ read: 0, queued: 0, gone: 2, failed: 0 }, AUTO),
      "2 e-mails are no longer in the mailbox.",
    );
    assert.equal(
      checkAgainText({ read: 0, queued: 0, gone: 0, failed: 3 }, AUTO),
      "3 e-mails couldn't be downloaded; try again later.",
    );
    assert.equal(
      checkAgainText({ read: 0, queued: 0, gone: 0, failed: 0 }, AUTO),
      "This parcel has no e-mails to read again.",
    );
  });

  test("reads the command's answer defensively", () => {
    assert.deepEqual(normalizeCheckAgain({ read: 2, queued: 1, gone: 0, failed: 1 }), {
      read: 2,
      queued: 1,
      gone: 0,
      failed: 1,
    });
    assert.deepEqual(normalizeCheckAgain({ read: 2.5, queued: "1", gone: -1 }), {
      read: 0,
      queued: 0,
      gone: 0,
      failed: 0,
    });
    assert.deepEqual(normalizeCheckAgain(null), { read: 0, queued: 0, gone: 0, failed: 0 });
  });
});
