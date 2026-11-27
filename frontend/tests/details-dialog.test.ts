import assert from "node:assert/strict";
import { describe, test } from "node:test";

import "./dom.ts";

import type { TemplateResult } from "lit";

import { ParcelsDetailsDialog } from "../src/details-dialog.ts";
import { normalizeDetails, normalizeSnapshot } from "../src/normalize.ts";
import type { Parcel, ParcelDetails, Snapshot } from "../src/types.ts";
import { makeParcel } from "./helpers.ts";
import { listener, renderText } from "./render.ts";

interface DetailsHost {
  hass: unknown;
  snapshot: Snapshot | null;
  _open: boolean;
  _busy: boolean;
  _parcelId: string | null;
  _details: ParcelDetails | null;
  _renderView(parcel: Parcel): TemplateResult;
  _renderActions(parcel: Parcel): TemplateResult;
  _undoDelivery(): void;
  _keepInferred(): void;
}

const MARKED = makeParcel({
  id: "p1",
  merchant: "Example Shop",
  status: "delivered",
  delivered_at: "2030-03-04T10:42:00+00:00",
  delivered_by_hand: true,
});

function dialog(parcel: Parcel = MARKED): DetailsHost {
  const host = new ParcelsDetailsDialog() as unknown as DetailsHost;
  host.snapshot = normalizeSnapshot({ parcels: [] });
  host.snapshot = { ...host.snapshot, parcels: [parcel] };
  host._parcelId = parcel.id;
  return host;
}

describe("a delivery marked by hand", () => {
  test("can be undone from the parcel's details", () => {
    const html = renderText(dialog()._renderView(MARKED));
    assert.match(html, /Marked delivered by hand\. Undo if it hasn't arrived\./);
    assert.match(
      html,
      /<button type="button" class="btn" data-undo-delivered aria-label="Undo marking Example Shop delivered" aria-disabled="false"> Undo <\/button>/,
    );
  });

  test("Undo waits for the action in progress", () => {
    const host = dialog();
    host._busy = true;
    assert.match(renderText(host._renderView(MARKED)), /data-undo-delivered [^>]*aria-disabled="true"/);
  });

  test("takes the delivery back through parcels.undo_delivery", async () => {
    const host = dialog();
    const calls: unknown[][] = [];
    host.hass = {
      callService: async (...args: unknown[]) => {
        calls.push(args);
      },
    };
    host._open = true;
    const undo = listener(host._renderView(MARKED), "data-undo-delivered");
    assert.equal(undo, host._undoDelivery);
    (undo as () => void).call(host);
    await Promise.resolve();
    assert.deepEqual(calls, [["parcels", "undo_delivery", { parcel_id: "p1" }, undefined, false]]);
  });

  test("isn't offered for a reported or an inferred delivery, nor on someone's private parcel", () => {
    const reported = { ...MARKED, delivered_by_hand: false };
    const inferred = { ...reported, inferred: true, inferred_reason: "shop" as const };
    const restricted = { ...MARKED, restricted: true };
    for (const parcel of [reported, restricted]) {
      const html = renderText(dialog(parcel)._renderView(parcel));
      assert.doesNotMatch(html, /data-undo-delivered|Marked delivered by hand/);
    }
    const html = renderText(dialog(inferred)._renderView(inferred));
    assert.doesNotMatch(html, /data-undo-delivered|Marked delivered by hand/);
    assert.match(html, /aria-label="Undo the inferred delivery of Example Shop"/);
  });

  test("shares its Undo with an inferred delivery", () => {
    const inferred = { ...MARKED, delivered_by_hand: false, inferred: true, inferred_reason: "shop" as const };
    const host = dialog(inferred);
    const view = host._renderView(inferred);
    assert.equal(listener(view, "Undo the inferred delivery of Example Shop"), host._undoDelivery);
    assert.equal(listener(view, "Keep the inferred delivery of Example Shop"), host._keepInferred);
  });
});

describe("an automatic merge", () => {
  const merged = makeParcel({
    id: "p2",
    merchant: "Example Shop",
    status: "delivered",
    auto_merged: { origin: "o2", at: "2030-03-04T10:42:00+00:00", reason: "same_order" },
  });

  function loaded(parcelId: string, differ: boolean): ParcelDetails | null {
    return normalizeDetails({ parcel: { id: parcelId }, merged_items_differ: differ });
  }

  test("says when its e-mails list different items", () => {
    const host = dialog(merged);
    const plain = /Merged automatically \(same order\)\. Check that it's one parcel\./;
    assert.match(renderText(host._renderView(merged)), plain);
    host._details = loaded("p2", false);
    assert.match(renderText(host._renderView(merged)), plain);
    host._details = loaded("p2", true);
    assert.match(
      renderText(host._renderView(merged)),
      /Merged automatically \(same order\), though its e-mails list different items\. Check that it's one parcel\./,
    );
    const unknown = { ...merged, auto_merged: { origin: "o2", at: "2030-03-04T10:42:00+00:00", reason: "" } };
    assert.match(
      renderText(host._renderView(unknown)),
      /Merged automatically, though its e-mails list different items\. Check that it's one parcel\./,
    );
  });

  test("goes by the details of the parcel shown", () => {
    const host = dialog(merged);
    host._details = loaded("p1", true);
    assert.doesNotMatch(renderText(host._renderView(merged)), /different items/);
  });
});

describe("Mark delivered", () => {
  test("is a secondary button, as it can be undone", () => {
    const parcel = makeParcel({ id: "p1", merchant: "Example Shop", status: "out_for_delivery" });
    const html = renderText(dialog(parcel)._renderActions(parcel));
    assert.match(html, /<button type="button" class="btn" aria-disabled="false">[^<]*<ha-icon icon="mdi:check"/);
    assert.doesNotMatch(html, /class="btn primary"/);
  });
});
