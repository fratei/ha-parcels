import assert from "node:assert/strict";
import { describe, test } from "node:test";

import { renderChip, type ChipOptions } from "../src/chip.ts";
import type { LocaleOptions } from "../src/format.ts";
import type { Parcel } from "../src/types.ts";
import { makeParcel } from "./helpers.ts";
import { renderText } from "./render.ts";

const GB: LocaleOptions = { language: "en-GB", hour12: false, timeZone: "Europe/Lisbon" };
const ignore = (): void => {};
const OPTIONS: ChipOptions = {
  locale: GB,
  onOpen: ignore,
  onUndoMerge: ignore,
  onKeepMerge: ignore,
  onUndoInferred: ignore,
  onKeepInferred: ignore,
};

function chip(overrides: Partial<Parcel>): string {
  return renderText(renderChip(makeParcel(overrides), OPTIONS));
}

describe("renderChip", () => {
  test("titles a Parcel-app parcel without a shop with its name", () => {
    const text = chip({ name: "Oak shelf", carrier: "ups" });
    assert.match(text, /<span class="chip-title">Oak shelf<\/span>/);
    assert.match(text, /aria-label="Oak shelf, carrier UPS, In transit"/);
  });

  test("says the seller isn't known only without a shop or a name", () => {
    assert.match(chip({ carrier: "ups" }), /<span class="chip-title unknown">Unknown seller<\/span>/);
    assert.match(
      chip({ merchant: "Example Shop", name: "Oak shelf" }),
      /<span class="chip-title">Example Shop<\/span>/,
    );
    assert.match(
      chip({ name: "Oak shelf", restricted: true }),
      /<span class="chip-title">Private parcel<\/span>/,
    );
  });
});
