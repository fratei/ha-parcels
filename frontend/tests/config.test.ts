import assert from "node:assert/strict";
import { describe, test } from "node:test";

import { cardTitle, listCardConfig, reviewCardConfig, weekCardConfig } from "../src/config.ts";
import { STRINGS } from "../src/strings.ts";

describe("card configuration", () => {
  test("archived parcels show by default, titles are trimmed and HA's own keys are ignored", () => {
    assert.deepEqual(weekCardConfig({ type: "custom:parcels-week-card" }), {
      type: "custom:parcels-week-card",
      title: undefined,
      show_archived: true,
    });
    assert.deepEqual(
      weekCardConfig({
        type: "custom:parcels-week-card",
        title: "  Deliveries ",
        show_archived: false,
        grid_options: { columns: 12 },
        visibility: [],
      }),
      { type: "custom:parcels-week-card", title: "Deliveries", show_archived: false },
    );
    assert.equal(listCardConfig({ type: "custom:parcels-list-card", title: null }).title, undefined);
    assert.equal(reviewCardConfig({ type: "custom:parcels-review-card", title: "" }).title, "");
  });

  test("invalid configurations are rejected with a readable message", () => {
    for (const config of [null, undefined, "title: x", ["a"], 3]) {
      assert.throws(() => weekCardConfig(config), { message: STRINGS.configInvalid });
      assert.throws(() => listCardConfig(config), { message: STRINGS.configInvalid });
      assert.throws(() => reviewCardConfig(config), { message: STRINGS.configInvalid });
    }
    assert.throws(() => listCardConfig({ title: 5 }), { message: STRINGS.configTitle });
    assert.throws(() => weekCardConfig({ show_archived: "no" }), { message: STRINGS.configShowArchived });
  });

  test("an empty title hides the header; no title uses the default", () => {
    assert.equal(cardTitle(undefined, "Parcels"), "Parcels");
    assert.equal(cardTitle("Mine", "Parcels"), "Mine");
    assert.equal(cardTitle("", "Parcels"), null);
  });
});
