import assert from "node:assert/strict";
import { describe, test } from "node:test";

import { errorMessage } from "../src/errors.ts";
import {
  carrierLabel,
  checkMeaning,
  humanize,
  inferredNotice,
  etaSourceLabel,
  kindLabel,
  mergeReasonLabel,
  noteMeaning,
  parcelAppName,
  parcelSubtitle,
  parcelTitle,
  reasonLabel,
  sourceLabel,
  statusLabel,
} from "../src/labels.ts";
import { STATUS_COLORS, isActiveStatus, statusColor, statusRank } from "../src/status.ts";
import { fmt } from "../src/strings.ts";
import { PARCEL_STATUSES } from "../src/types.ts";
import { safeHttpsUrl } from "../src/url.ts";
import { makeParcel } from "./helpers.ts";

describe("status colours", () => {
  test("map each status to a theme colour with a fallback", () => {
    assert.equal(statusColor("ordered"), "var(--secondary-text-color, #727272)");
    assert.equal(statusColor("shipped"), "var(--info-color, #039be5)");
    assert.equal(statusColor("in_transit"), "var(--info-color, #039be5)");
    assert.equal(statusColor("out_for_delivery"), "var(--warning-color, #ffa600)");
    assert.equal(statusColor("delivered"), "var(--success-color, #43a047)");
    assert.equal(statusColor("attempted"), "var(--error-color, #db4437)");
    assert.equal(statusColor("exception"), "var(--error-color, #db4437)");
    assert.equal(statusColor("ready_for_pickup"), "var(--purple-color, #926bc7)");
    assert.equal(statusColor("returned"), "var(--secondary-text-color, #727272)");
  });

  test("cover every status and default to grey", () => {
    for (const status of PARCEL_STATUSES) {
      assert.match(STATUS_COLORS[status], /^var\(--[a-z-]+-color, #[0-9a-f]{6}\)$/);
    }
    assert.equal(statusColor("teleported"), "var(--secondary-text-color, #727272)");
    assert.equal(statusColor("constructor"), "var(--secondary-text-color, #727272)");
  });

  test("ranks and activity follow the integration", () => {
    assert.equal(statusRank("ordered"), 0);
    assert.equal(statusRank("out_for_delivery"), 3);
    assert.equal(statusRank("delivered"), 4);
    assert.equal(statusRank("toString"), 0);
    assert.deepEqual(
      PARCEL_STATUSES.filter((status) => !isActiveStatus(status)),
      ["delivered", "returned", "cancelled"],
    );
  });
});

describe("safeHttpsUrl", () => {
  test("allows https URLs", () => {
    assert.equal(
      safeHttpsUrl("https://tracking.example.com/track?id=TEST0001"),
      "https://tracking.example.com/track?id=TEST0001",
    );
    assert.equal(safeHttpsUrl("  HTTPS://Example.com  "), "https://example.com/");
  });

  test("rejects everything else", () => {
    for (const value of [
      "http://example.com/track",
      "javascript:alert(1)",
      "JaVaScRiPt:alert(1)",
      "data:text/html,hello",
      "ftp://example.com/file",
      "//example.com/track",
      "/relative/path",
      "https://user:secret@example.com/",
      "https://",
      "",
      "   ",
      null,
      undefined,
      42,
      { href: "https://example.com" },
    ]) {
      assert.equal(safeHttpsUrl(value), null, String(value));
    }
  });
});

describe("labels", () => {
  test("title falls back from merchant to carrier to tracking number", () => {
    assert.equal(parcelTitle(makeParcel({ merchant: "Example Shop", carrier: "dhl" })), "Example Shop");
    assert.equal(parcelTitle(makeParcel({ merchant: "  ", carrier_name: "Test Express" })), "Test Express");
    assert.equal(parcelTitle(makeParcel({ carrier: "dhl" })), "DHL");
    assert.equal(parcelTitle(makeParcel({ carrier: "acme_post" })), "Acme post");
    assert.equal(parcelTitle(makeParcel({ carrier: "other", tracking_number: "TEST0001" })), "TEST0001");
    assert.equal(parcelTitle(makeParcel({ tracking_number: " TEST0002 " })), "TEST0002");
    assert.equal(parcelTitle(makeParcel()), "Parcel");
  });

  test("the Parcel app name comes after the merchant and before the carrier", () => {
    assert.equal(parcelTitle(makeParcel({ merchant: "Example Shop", name: "Blue mug" })), "Example Shop");
    assert.equal(parcelTitle(makeParcel({ name: " Blue mug ", carrier: "dhl" })), "Blue mug");
    assert.equal(parcelTitle(makeParcel({ name: "  ", carrier: "dhl" })), "DHL");
    assert.equal(parcelTitle(makeParcel({ restricted: true, name: "Blue mug" })), "Private parcel");
    assert.equal(parcelSubtitle(makeParcel({ name: "Blue mug", carrier: "ups" })), "UPS");
  });

  test("the Parcel app name is shown apart only when the title isn't it", () => {
    assert.equal(parcelAppName(makeParcel({ merchant: "Example Shop", name: " Blue mug " })), "Blue mug");
    assert.equal(parcelAppName(makeParcel({ name: "Blue mug", carrier: "dhl" })), null);
    assert.equal(parcelAppName(makeParcel({ merchant: "Example Shop", name: "Example Shop" })), null);
    assert.equal(parcelAppName(makeParcel({ merchant: "Example Shop", name: "  " })), null);
    assert.equal(
      parcelAppName(makeParcel({ restricted: true, merchant: "Example Shop", name: "Blue mug" })),
      null,
    );
  });

  test("an expected date from the Parcel app says so", () => {
    assert.equal(etaSourceLabel(makeParcel({ eta_source: "parcelapp" })), "Parcel app");
    for (const source of ["parser", "ai", "manual", "seventeentrack", null] as const) {
      assert.equal(etaSourceLabel(makeParcel({ eta_source: source })), null, String(source));
    }
  });

  test("restricted parcels are always a private parcel", () => {
    const parcel = makeParcel({ restricted: true, merchant: "Example Shop", carrier: "dhl" });
    assert.equal(parcelTitle(parcel), "Private parcel");
    assert.equal(parcelSubtitle(parcel), "DHL");
    assert.equal(parcelTitle(makeParcel({ restricted: true })), "Private parcel");
  });

  test("subtitle shows the carrier unless it's already the title", () => {
    assert.equal(parcelSubtitle(makeParcel({ merchant: "Example Shop", carrier: "ups" })), "UPS");
    assert.equal(parcelSubtitle(makeParcel({ carrier: "ups" })), null);
    assert.equal(parcelSubtitle(makeParcel({ merchant: "Example Shop" })), null);
    assert.equal(carrierLabel({ carrier: "dhl", carrier_name: "DHL Parcel" }), "DHL Parcel");
    assert.equal(carrierLabel({ carrier: "other", carrier_name: null }), null);
  });

  test("statuses, kinds, sources and reasons are readable", () => {
    assert.equal(statusLabel("out_for_delivery"), "Out for delivery");
    assert.equal(statusLabel("held_somewhere"), "Held somewhere");
    assert.equal(kindLabel("not_parcel"), "Not about a parcel");
    assert.equal(sourceLabel("seventeentrack"), "17TRACK");
    assert.equal(sourceLabel("parcelapp"), "Parcel app");
    assert.equal(sourceLabel("quiet"), "No news for three weeks");
    assert.equal(reasonLabel("unknown_sender"), "Unknown sender");
    assert.equal(reasonLabel("ai_timeout"), "The local AI took too long on this e-mail");
    // Items stored before the timeout reason existed keep their label.
    assert.equal(reasonLabel("ai_unavailable"), "The local AI wasn't available");
    assert.equal(reasonLabel("brand_new_reason"), "Brand new reason");
    assert.equal(reasonLabel("The sender isn't known."), "The sender isn't known.");
    assert.equal(reasonLabel(""), "");
    assert.equal(reasonLabel(null), "");
    assert.equal(reasonLabel("__proto__"), "__proto__");
    assert.equal(mergeReasonLabel("same_reference"), "same shipment reference");
    assert.equal(humanize("low-confidence"), "Low confidence");
  });

  test("a note on an AI answer has a one-line meaning; an unknown one has none", () => {
    assert.match(noteMeaning("carrier_unproven") ?? "", /^The shop, such as Amazon, was given as the carrier/);
    assert.match(noteMeaning("tracking_added_by_detector") ?? "", /detector/);
    assert.equal(noteMeaning("brand_new_note"), null);
    assert.equal(noteMeaning("__proto__"), null);
    assert.equal(noteMeaning(""), null);
    assert.equal(noteMeaning(null), null);
  });

  test("a failed check on an AI answer has a one-line meaning; an unknown one has none", () => {
    assert.match(checkMeaning("tracking_not_in_email") ?? "", /^A tracking number isn't in the e-mail/);
    assert.equal(checkMeaning("merchant_cut"), checkMeaning("pickup_code_cut"));
    assert.match(checkMeaning("merchant_cut") ?? "", /cut item ends with "…"\.$/);
    assert.equal(checkMeaning("carrier_unproven"), null);
    assert.equal(checkMeaning("brand_new_check"), null);
    assert.equal(checkMeaning("__proto__"), null);
    assert.equal(checkMeaning(""), null);
    assert.equal(checkMeaning(null), null);
  });

  test("an inferred delivery says why", () => {
    const quiet = inferredNotice(makeParcel({ inferred: true, inferred_reason: "quiet" }));
    assert.match(quiet, /no news for three weeks/);
    assert.match(quiet, /Undo/);
    const shop = inferredNotice(makeParcel({ inferred: true, inferred_reason: "shop" }));
    assert.match(shop, /another parcel from this shop/);
    const sentBack = inferredNotice(makeParcel({ inferred: true, inferred_reason: "return" }));
    assert.match(sentBack, /sending its items back/);
    // Parcels sent before the reason existed.
    assert.equal(inferredNotice(makeParcel({ inferred: true })), shop);
  });

  test("fmt fills placeholders and leaves unknown ones", () => {
    assert.equal(fmt("{a} and {b}", { a: "x", b: 2 }), "x and 2");
    assert.equal(fmt("{a} {missing}", { a: "x" }), "x {missing}");
  });
});

describe("errorMessage", () => {
  test("uses the error's message", () => {
    assert.equal(errorMessage({ code: "not_found", message: "Parcel not found" }), "Parcel not found");
    assert.equal(errorMessage(new Error("Boom")), "Boom");
    assert.equal(errorMessage("Plain text"), "Plain text");
    assert.equal(errorMessage({ code: "unknown_command" }), "unknown_command");
    assert.equal(errorMessage(null), "Unknown error");
    assert.equal(errorMessage({ message: "" }), "Unknown error");
  });
});
