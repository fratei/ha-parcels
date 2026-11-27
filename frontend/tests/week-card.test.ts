import assert from "node:assert/strict";
import { describe, test } from "node:test";

import "./dom.ts";

import type { ParcelFilter } from "../src/filter.ts";
import { ParcelsListCard } from "../src/list-card.ts";
import { normalizeSnapshot } from "../src/normalize.ts";
import type { WeekLayout } from "../src/placement.ts";
import { REVIEW_DONE_EVENT, SHOW_REVIEW_EVENT, type ReviewDone } from "../src/review-state.ts";
import { STRINGS } from "../src/strings.ts";
import type { MergeSuggestion, Parcel, ReviewItem, Snapshot } from "../src/types.ts";
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
  render(): unknown;
  _onReviewDone(event: Event): void;
  announce(message: string): void;
  renderRoot: unknown;
  hidden: boolean;
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
  suggestions?: number;
  filter?: ParcelFilter;
}

function weekCard(parcels: readonly Parcel[], options: Options = {}): WeekHost {
  const card = new ParcelsWeekCard() as unknown as WeekHost;
  const settings = { today: TODAY, time_zone: "Europe/Lisbon", user_is_admin: options.admin ?? true };
  card._snapshots.snapshot = {
    ...normalizeSnapshot({ settings }),
    parcels: [...parcels],
    review: Array.from({ length: options.review ?? 0 }, (_, index) => ({ id: `r${index}` }) as ReviewItem),
    merge_suggestions: Array.from(
      { length: options.suggestions ?? 0 },
      (_, index) => ({ id: `m${index}` }) as MergeSuggestion,
    ),
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

  test("tells everyone else about the possible duplicates theirs to decide", () => {
    assert.equal(plain(attention(weekCard(NOT_LATE, { admin: false, suggestions: 1 }))), "1 to review");
    const both = weekCard(LATE, { admin: false, review: 3, suggestions: 2 });
    assert.equal(plain(attention(both)), "2 late · 2 to review");
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

describe("after the last review decision hides the review card", () => {
  const CHIP = '.chip[data-parcels~="p2"] button.chip-main';
  const HEADING = "h2.title";
  const MERGED: ReviewDone = { parcels: ["p2"], message: "Merged. Nothing else to review." };

  interface Fake {
    readonly name: string;
    focus(): void;
  }

  interface Page {
    readonly card: WeekHost;
    readonly announced: string[];
    focused(): string | null;
  }

  /**
   * A connected week card that shows `elements`. Focusing one makes it the
   * card's focused element, unless the browser refuses (`refuses`).
   */
  function page(elements: readonly string[], refuses = false): Page {
    const card = weekCard([]);
    const root: { activeElement: Fake | null } = { activeElement: null };
    const shown = new Map<string, Fake>();
    for (const name of elements) {
      const element: Fake = {
        name,
        focus: () => {
          if (!refuses) {
            root.activeElement = element;
          }
        },
      };
      shown.set(name, element);
    }
    card.renderRoot = { querySelector: (selector: string) => shown.get(selector) ?? null };
    card.hidden = false;
    Object.defineProperty(card, "shadowRoot", { value: root });
    Object.defineProperty(card, "isConnected", { value: true });
    const announced: string[] = [];
    card.announce = (message) => announced.push(message);
    return { card, announced, focused: () => root.activeElement?.name ?? null };
  }

  function done(detail: ReviewDone): CustomEvent<ReviewDone> {
    return new CustomEvent(REVIEW_DONE_EVENT, { detail, cancelable: true });
  }

  /** Node has no CSS.escape, which chip selectors use. */
  function withCss(body: () => void): void {
    const host = globalThis as { CSS?: unknown };
    host.CSS = { escape: (value: string) => value };
    try {
      body();
    } finally {
      delete host.CSS;
    }
  }

  test("both cards have a status region and a heading that can take focus", () => {
    const week = renderText(weekCard([]).render());
    assert.match(week, /<h2 class="title" tabindex="-1">Parcels<\/h2>/);
    assert.match(week, /<div class="sr-only" role="status"><\/div> <\/ha-card>/);

    const list = new ParcelsListCard() as unknown as WeekHost;
    list._snapshots.snapshot = normalizeSnapshot({ settings: { today: TODAY, time_zone: "Europe/Lisbon" } });
    const html = renderText(list.render());
    assert.match(html, /<h2 class="title" tabindex="-1">No date yet<\/h2>/);
    assert.match(html, /<div class="sr-only" role="status"><\/div> <\/ha-card>/);
  });

  test("focus goes to the decided parcel's chip, and the card says what happened", () => {
    withCss(() => {
      const { card, announced, focused } = page([CHIP, HEADING]);
      const event = done(MERGED);
      card._onReviewDone(event);
      assert.equal(event.defaultPrevented, true);
      assert.equal(focused(), CHIP);
      assert.deepEqual(announced, [MERGED.message]);
    });
  });

  test("a card without the parcel's chip leaves it to another card", () => {
    withCss(() => {
      const { card, announced, focused } = page([HEADING]);
      const event = done(MERGED);
      card._onReviewDone(event);
      assert.equal(event.defaultPrevented, false);
      assert.equal(focused(), null);
      assert.deepEqual(announced, []);
    });
  });

  test("without parcels, focus goes to the card's heading, else to its Add button", () => {
    const { card, announced, focused } = page([HEADING, "[data-focus-fallback]"]);
    const event = done({ parcels: [], message: "Kept apart. Nothing else to review." });
    card._onReviewDone(event);
    assert.equal(event.defaultPrevented, true);
    assert.equal(focused(), HEADING);
    assert.deepEqual(announced, ["Kept apart. Nothing else to review."]);

    const untitled = page(["[data-focus-fallback]"]);
    const quiet = done({ parcels: [], message: "" });
    untitled.card._onReviewDone(quiet);
    assert.equal(quiet.defaultPrevented, true);
    assert.equal(untitled.focused(), "[data-focus-fallback]");
    assert.deepEqual(untitled.announced, []);
  });

  test("isn't taken by a hidden card, a card without parcels yet, or once another took it", () => {
    const hidden = page([HEADING]);
    hidden.card.hidden = true;
    const first = done({ parcels: [], message: "x" });
    hidden.card._onReviewDone(first);
    assert.equal(first.defaultPrevented, false);
    assert.equal(hidden.focused(), null);

    const loading = page([HEADING]);
    loading.card._snapshots.snapshot = null;
    loading.card._onReviewDone(first);
    assert.equal(first.defaultPrevented, false);
    assert.equal(loading.focused(), null);

    const taken = done({ parcels: [], message: "x" });
    taken.preventDefault();
    const late = page([HEADING]);
    late.card._onReviewDone(taken);
    assert.equal(late.focused(), null);
    assert.deepEqual(late.announced, []);
  });

  test("isn't taken when focus didn't move", () => {
    const { card, announced } = page([HEADING], true);
    const event = done({ parcels: [], message: "x" });
    card._onReviewDone(event);
    assert.equal(event.defaultPrevented, false);
    assert.deepEqual(announced, []);
  });
});
