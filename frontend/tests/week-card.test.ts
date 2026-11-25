import assert from "node:assert/strict";
import { describe, test } from "node:test";

import "./dom.ts";

import type { ParcelFilter } from "../src/filter.ts";
import { normalizeSnapshot } from "../src/normalize.ts";
import type { WeekLayout } from "../src/placement.ts";
import { SHOW_REVIEW_EVENT } from "../src/review-state.ts";
import { STRINGS } from "../src/strings.ts";
import type { Parcel, ReviewItem, Snapshot } from "../src/types.ts";
import { ParcelsWeekCard } from "../src/week-card.ts";
import { makeParcel } from "./helpers.ts";
import { listener, renderText } from "./render.ts";

interface WeekHost {
  _snapshots: { snapshot: Snapshot | null };
  _filter: ParcelFilter;
  _narrow: boolean;
  _weekOffset: number;
  _layout(): WeekLayout | null;
  _renderAttention(snapshot: Snapshot): unknown;
  _renderStacked(snapshot: Snapshot, layout: WeekLayout, range: string): unknown;
  _showLate(): void;
  _showReview(): void;
  showActionError(message: string): void;
}

/** Wednesday 6 March 2030. */
const TODAY = "2030-03-06";

function expectedOn(id: string, day: string, overrides: Partial<Parcel> = {}): Parcel {
  return makeParcel({ id, merchant: `Shop ${id}`, eta_start: day, eta_end: day, ...overrides });
}

const LATE = [expectedOn("a", "2030-03-04"), expectedOn("b", "2030-03-05")];
const NOT_LATE = [
  expectedOn("c", TODAY),
  expectedOn("d", "2030-03-04", { status: "delivered", delivered_at: "2030-03-04T10:00:00+00:00" }),
  expectedOn("e", "2030-03-04", { status: "cancelled" }),
  expectedOn("f", "2030-03-04", { status: "returned" }),
  expectedOn("g", "2030-03-04", { archived: true }),
];

interface Options {
  admin?: boolean;
  review?: number;
  filter?: ParcelFilter;
}

function weekCard(parcels: readonly Parcel[], options: Options = {}): WeekHost {
  const card = new ParcelsWeekCard() as unknown as WeekHost;
  const settings = { today: TODAY, time_zone: "Europe/Lisbon", user_is_admin: options.admin ?? true };
  card._snapshots.snapshot = {
    ...normalizeSnapshot({ settings }),
    parcels: [...parcels],
    review: Array.from({ length: options.review ?? 0 }, (_, index) => ({ id: `r${index}` }) as ReviewItem),
  };
  card._filter = options.filter ?? "all";
  return card;
}

function attention(card: WeekHost): unknown {
  const snapshot = card._snapshots.snapshot;
  assert.ok(snapshot);
  return card._renderAttention(snapshot);
}

/** The visible text, without tags. */
function plain(value: unknown): string {
  return renderText(value)
    .replace(/<[^>]*>/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

describe("the week card's attention line", () => {
  test("counts the late parcels and what needs review", () => {
    const card = weekCard([...LATE, ...NOT_LATE], { review: 1 });
    assert.equal(plain(attention(card)), "2 late · 1 to review");
    assert.match(renderText(attention(card)), /^<p class="attention">/);
  });

  test("tells only administrators what needs review", () => {
    assert.equal(plain(attention(weekCard(LATE, { review: 2 }))), "2 late · 2 to review");
    assert.equal(plain(attention(weekCard(LATE, { admin: false, review: 2 }))), "2 late");
    assert.equal(plain(attention(weekCard(NOT_LATE, { review: 1 }))), "1 to review");
  });

  test("is left out when nothing is late or to review", () => {
    assert.equal(renderText(attention(weekCard(NOT_LATE))), "");
    assert.equal(renderText(attention(weekCard(NOT_LATE, { admin: false, review: 3 }))), "");
  });

  test("counts only the late parcels the chosen filter shows", () => {
    assert.equal(plain(attention(weekCard(LATE, { filter: "recent" }))), "2 late");
    assert.equal(plain(attention(weekCard(LATE, { filter: "completed", review: 1 }))), "1 to review");
  });

  test("follows a new filter or snapshot on the same card", () => {
    const card = weekCard(LATE);
    assert.equal(plain(attention(card)), "2 late");
    card._filter = "completed";
    assert.equal(plain(attention(card)), "");
    card._filter = "all";
    assert.equal(plain(attention(card)), "2 late");
    const snapshot = card._snapshots.snapshot;
    assert.ok(snapshot);
    card._snapshots.snapshot = { ...snapshot, parcels: [LATE[0] as Parcel] };
    assert.equal(plain(attention(card)), "1 late");
  });

  test("its late link goes back to this week, where they are", () => {
    const card = weekCard(LATE);
    assert.equal(listener(attention(card), STRINGS.attentionLateLabel), card._showLate);
    card._weekOffset = -2;
    card._showLate();
    assert.equal(card._weekOffset, 0);
  });

  test("its review link asks the review card to show Needs review, or says to add one", () => {
    const card = weekCard([], { review: 1 });
    assert.equal(listener(attention(card), STRINGS.attentionReviewLabel), card._showReview);
    const errors: string[] = [];
    card.showActionError = (message) => errors.push(message);
    const host = globalThis as { window?: unknown };
    const saved = host.window;
    const page = new EventTarget();
    host.window = page;
    try {
      card._showReview();
      assert.deepEqual(errors, [STRINGS.reviewCardMissing]);
      page.addEventListener(SHOW_REVIEW_EVENT, (event) => event.preventDefault());
      card._showReview();
      assert.equal(errors.length, 1);
    } finally {
      host.window = saved;
    }
  });
});

describe("the stacked week on a narrow card", () => {
  function stacked(parcels: readonly Parcel[]): string {
    const card = weekCard(parcels);
    card._narrow = true;
    const snapshot = card._snapshots.snapshot;
    const layout = card._layout();
    assert.ok(snapshot && layout);
    return renderText(card._renderStacked(snapshot, layout, "range"));
  }

  test("lists the late parcels in a Late group before today", () => {
    const text = stacked([...LATE, expectedOn("c", TODAY)]);
    const group = text.indexOf('<li class="day late-group">');
    const today = text.indexOf('aria-current="date"');
    assert.ok(group >= 0 && group < today, text);
    assert.equal(plain(text.slice(group, today)).startsWith(`${STRINGS.lateGroup} `), true);
    for (const id of ["a", "b"]) {
      const chip = `data-parcel-id="${id}"`;
      const at = text.indexOf(chip);
      assert.ok(group < at && at < today, `${id} is in the Late group`);
      assert.equal(text.indexOf(chip, at + 1), -1, `${id} is shown once`);
    }
    assert.ok(text.indexOf('data-parcel-id="c"') > today);
  });

  test("shows today as free when only late parcels are there", () => {
    const text = stacked(LATE);
    const today = text.slice(text.lastIndexOf("<li", text.indexOf('aria-current="date"')));
    assert.match(today, /^<li class="day compact today"/);
    assert.ok(plain(today).includes(STRINGS.noDeliveriesThisDay));
  });

  test("has no Late group when nothing is late", () => {
    assert.equal(stacked(NOT_LATE).includes("late-group"), false);
  });
});
