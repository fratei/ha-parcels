import assert from "node:assert/strict";
import { describe, test } from "node:test";

import { readDeepLink, withoutDeepLink } from "../src/url.ts";

describe("readDeepLink", () => {
  test("reads the parcel or the return a notification opens", () => {
    assert.deepEqual(readDeepLink("?parcel=p_00000000002a"), {
      kind: "parcel",
      id: "p_00000000002a",
    });
    assert.deepEqual(readDeepLink("?kiosk&return=ret_0000000000b1&external_auth=1"), {
      kind: "return",
      id: "ret_0000000000b1",
    });
  });

  test("ignores anything that isn't a parcel or a return ID", () => {
    for (const search of [
      "",
      "?",
      "?kiosk",
      "?parcel=",
      "?parcel=ret_0000000000b1",
      "?return=p_00000000002a",
      "?parcel=p_00000000002A",
      "?parcel=p_00000000002a%3Cb%3E",
      "?parcel=..%2Fconfig",
      "?parcels=p_00000000002a",
    ]) {
      assert.equal(readDeepLink(search), null, search);
    }
  });
});

describe("withoutDeepLink", () => {
  test("drops the link and keeps the dashboard's own parameters as written", () => {
    assert.equal(withoutDeepLink("?parcel=p_00000000002a"), "");
    assert.equal(withoutDeepLink("?kiosk&parcel=p_00000000002a"), "?kiosk");
    assert.equal(
      withoutDeepLink("?external_auth=1&return=ret_0000000000b1&edit=1"),
      "?external_auth=1&edit=1",
    );
    // A link that can't be opened is dropped too.
    assert.equal(withoutDeepLink("?kiosk&parcel=nonsense"), "?kiosk");
  });

  test("leaves a query without a link untouched", () => {
    for (const search of ["", "?", "?kiosk", "?kiosk=&a=b%20c", "?parcels=p_00000000002a"]) {
      assert.equal(withoutDeepLink(search), search);
    }
  });
});
