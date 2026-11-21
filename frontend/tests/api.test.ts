import assert from "node:assert/strict";
import { describe, test } from "node:test";

import { callParcelsServiceForParcel } from "../src/api.ts";
import type { HomeAssistant } from "../src/types.ts";

function fakeHass(result: unknown, calls: unknown[][]): HomeAssistant {
  return {
    connection: {} as HomeAssistant["connection"],
    callWS: () => Promise.reject(new Error("not used")),
    callService: (...args: unknown[]) => {
      calls.push(args);
      return Promise.resolve(result);
    },
  };
}

describe("services that answer", () => {
  test("ask for the response and read the parcel it names", async () => {
    const calls: unknown[][] = [];
    const hass = fakeHass({ context: { id: "c1" }, response: { parcel_id: "p2" } }, calls);
    assert.equal(await callParcelsServiceForParcel(hass, "split", { parcel_id: "p1", origins: ["m1"] }), "p2");
    assert.deepEqual(calls, [["parcels", "split", { parcel_id: "p1", origins: ["m1"] }, undefined, false, true]]);
  });

  test("give null when the response names no parcel", async () => {
    for (const result of [undefined, {}, { response: null }, { response: { parcel_id: 7 } }, { response: { parcel_id: "" } }]) {
      assert.equal(await callParcelsServiceForParcel(fakeHass(result, []), "merge", {}), null);
    }
  });
});
