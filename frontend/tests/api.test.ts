import assert from "node:assert/strict";
import { readdirSync, readFileSync } from "node:fs";
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

describe("WebSocket commands", () => {
  test("the cards send only commands the integration registers", () => {
    const websocket = readFileSync(new URL("../../custom_components/parcels/websocket.py", import.meta.url), "utf8");
    const registered = new Set([...websocket.matchAll(/f"\{DOMAIN\}\/([a-z_/]+)"/g)].map((match) => match[1]));
    const src = new URL("../src/", import.meta.url);
    const sent = new Set<string>();
    for (const name of readdirSync(src).filter((file) => file.endsWith(".ts"))) {
      const text = readFileSync(new URL(name, src), "utf8");
      const calls = /(?:callParcelsCommand(?:<[^>]*>)?\(\s*hass,|this\._command\(\s*[\w.]+,)\s*"([^"]+)"/g;
      for (const match of text.matchAll(calls)) {
        sent.add(match[1] ?? "");
      }
    }
    for (const command of [
      "get",
      "origin/remove",
      "review/accept",
      "review/trust_sender",
      "mail/retry_failed",
      "mail/dismiss_failed",
    ]) {
      assert.ok(sent.has(command), command);
    }
    assert.deepEqual(
      [...sent].filter((command) => !registered.has(command)),
      [],
    );
  });
});
