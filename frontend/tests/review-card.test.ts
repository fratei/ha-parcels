import assert from "node:assert/strict";
import { describe, test } from "node:test";

import "./dom.ts";

import type { TemplateResult } from "lit";

import { suggestionToForm, type FormProblem, type SuggestionForm } from "../src/forms.ts";
import { normalizeSnapshot } from "../src/normalize.ts";
import { ParcelsReviewCard } from "../src/review-card.ts";
import { REVIEW_DONE_EVENT, SHOW_REVIEW_EVENT, type ReviewDone } from "../src/review-state.ts";
import { STRINGS } from "../src/strings.ts";
import type {
  FilteredItem,
  MergeSuggestion,
  ReviewItem,
  Snapshot,
  Suggestion,
} from "../src/types.ts";
import { listener, renderText } from "./render.ts";

interface EditFormHost {
  _editForm: SuggestionForm;
  _editProblem: FormProblem | null;
  _renderEditForm(item: ReviewItem, busy: boolean): TemplateResult;
}

const SUGGESTION: Suggestion = {
  kind: "shipped",
  merchant: "Example Shop",
  carrier: "dhl",
  tracking_numbers: ["TEST0001", "TEST0002"],
  order_numbers: ["ORDER-1"],
  reference: null,
  eta_start: null,
  eta_end: null,
  window_start: null,
  window_end: null,
  pickup_point: null,
  pickup_code: null,
  items: [],
  amazon_shipment_id: null,
};

const ITEM = {
  id: "review-1",
  created: "2030-03-04T09:00:00+00:00",
  received: null,
  sender: "shop@example.com",
  sender_domain: "example.com",
  sender_org: "example.com",
  subject: "Your order",
  mailbox_owner: null,
  reason: "unknown_sender",
  authenticated: true,
  trusted_sender: false,
  known_sender: false,
  free_mail: false,
  checks: null,
  fill: false,
  errors: [],
  notes: [],
  source: "parser",
  suggestion: SUGGESTION,
} satisfies ReviewItem;

function editForm(problem: FormProblem | null = null): string {
  const card = new ParcelsReviewCard() as unknown as EditFormHost;
  card._editForm = suggestionToForm(SUGGESTION);
  card._editProblem = problem;
  return renderText(card._renderEditForm(ITEM, false));
}

describe("review Edit form", () => {
  // Enter in a single-line input submits the form, which accepted the e-mail.
  for (const [name, hint] of [
    ["tracking_numbers", "edit-hint-tracking"],
    ["order_numbers", "edit-hint-orders"],
  ]) {
    test(`${name} takes one value per line, so Enter adds a line`, () => {
      const html = editForm();
      assert.doesNotMatch(html, new RegExp(`<input[^>]*name="${name}"`));
      assert.match(html, new RegExp(`<textarea[^>]*name="${name}"[^>]*aria-describedby="${hint}"`));
      assert.match(html, new RegExp(`id="${hint}">Separate with commas or new lines.<`));
    });
  }

  test("other fields stay single-line", () => {
    const html = editForm();
    assert.match(html, /<input type="text" name="merchant"/);
    assert.match(html, /<input type="text" name="reference"/);
    assert.match(html, /<textarea[^>]*name="items"/);
  });

  test("a wrong date points to its error", () => {
    const html = editForm({ field: "eta_end", message: "Wrong date" });
    assert.match(html, /<input type="date" name="eta_end"[^>]*aria-invalid="true" aria-describedby="edit-error"/);
    assert.match(html, /<input type="date" name="eta_start"[^>]*aria-invalid="false" \/>/);
    assert.match(html, /id="edit-error" role="alert"> <span class="grow">Wrong date</);
  });
});

describe("the week card's link to Needs review", () => {
  interface ShowReviewHost {
    _tab: string;
    _snapshots: { snapshot: Snapshot | null };
    _onShowReview(event: Event): void;
  }

  function reviewCard(admin: boolean): ShowReviewHost {
    const card = new ParcelsReviewCard() as unknown as ShowReviewHost;
    card._snapshots.snapshot = normalizeSnapshot({ settings: { user_is_admin: admin } });
    card._tab = "filtered";
    return card;
  }

  const request = (): Event => new CustomEvent(SHOW_REVIEW_EVENT, { cancelable: true });

  test("opens Needs review on an administrator's card, which takes the request", () => {
    const card = reviewCard(true);
    const event = request();
    card._onShowReview(event);
    assert.equal(card._tab, "review");
    assert.equal(event.defaultPrevented, true);
  });

  test("is left to another card when this one is hidden or another took it", () => {
    const hidden = reviewCard(false);
    const event = request();
    hidden._onShowReview(event);
    assert.equal(hidden._tab, "filtered");
    assert.equal(event.defaultPrevented, false);

    const first = reviewCard(true);
    const second = reviewCard(true);
    first._onShowReview(event);
    second._onShowReview(event);
    assert.equal(first._tab, "review");
    assert.equal(second._tab, "filtered");
  });
});

describe("the card of a user who isn't an administrator", () => {
  interface CardHost {
    _tab: string;
    _snapshots: { snapshot: Snapshot | null };
    render(): unknown;
    getCardSize(): number;
    showActionError(message: string): void;
    _onShowReview(event: Event): void;
  }

  const SAME_ORDER = {
    id: "m1",
    reason: "same_order",
    merchant: "Example Shop",
    day: null,
    parcel: { id: "p1", merchant: "Example Shop", tracking_number: "TEST0001", status: "out_for_delivery" },
    candidates: [{ id: "p2", merchant: "Example Shop", status: "shipped", private: true }],
  };

  function card(admin: boolean, suggestions: unknown[] = []): CardHost {
    const host = new ParcelsReviewCard() as unknown as CardHost;
    host._snapshots.snapshot = normalizeSnapshot({
      settings: { user_is_admin: admin },
      merge_suggestions: suggestions,
    });
    return host;
  }

  test("shows Needs review alone, with the suggestions theirs to decide", () => {
    const html = renderText(card(false, [SAME_ORDER]).render());
    assert.doesNotMatch(html, /role="tablist"/);
    assert.doesNotMatch(html, /panel-filtered/);
    assert.match(
      html,
      /<div class="panel" role="region" id="panel-review" aria-label="Needs review" tabindex="0">/,
    );
    assert.match(html, /data-item-id="m1"/);
    assert.match(html, /> Merge </);
    assert.match(html, /> Keep apart </);
  });

  test("is hidden while none is theirs to decide", () => {
    const host = card(false);
    assert.equal(renderText(host.render()), "");
    assert.equal(host.getCardSize(), 0);
  });

  test("stays while it says why their decision failed", () => {
    const host = card(false);
    host.showActionError("Couldn't merge");
    assert.match(renderText(host.render()), /Couldn't merge/);
    assert.ok(host.getCardSize() > 0);
  });

  test("takes the week card's request when it has their suggestions", () => {
    const event = new CustomEvent(SHOW_REVIEW_EVENT, { cancelable: true });
    card(false)._onShowReview(event);
    assert.equal(event.defaultPrevented, false);
    card(false, [SAME_ORDER])._onShowReview(event);
    assert.equal(event.defaultPrevented, true);
  });

  test("an administrator's card keeps both lists", () => {
    const html = renderText(card(true, [SAME_ORDER]).render());
    assert.match(html, /role="tablist"/);
    assert.match(html, /role="tabpanel" id="panel-review" aria-labelledby="tab-review"/);
    assert.match(html, /role="tabpanel" id="panel-filtered"/);
  });

  describe("after their last decision", () => {
    interface HandOffHost extends CardHost {
      _hass: unknown;
      _status: { icon: string; text: string; tab: string } | null;
      _handingOff: boolean;
      _letGo: boolean;
      _decision: { suggestionId: string; done: Promise<ReviewDone | null> } | null;
      hidden: boolean;
      _renderMergeSuggestion(suggestion: MergeSuggestion, index: number): unknown;
      _settleDecision(): void;
      _startsHandOff(): boolean;
      _handOff(): Promise<void>;
    }

    const MERGED: ReviewDone = { parcels: ["p2"], message: STRINGS.reviewDoneMerged };
    const KEPT: ReviewDone = { parcels: ["p1"], message: STRINGS.reviewDoneKeptApart };

    function decided(done: ReviewDone | null): HandOffHost["_decision"] {
      return { suggestionId: "m1", done: Promise.resolve(done) };
    }

    /** A connected card; focus is in it unless `focused` is false. */
    function connected(suggestions: unknown[] = [], focused = true, admin = false): HandOffHost {
      const host = card(admin, suggestions) as unknown as HandOffHost;
      Object.defineProperty(host, "isConnected", { value: true });
      Object.defineProperty(host, "shadowRoot", {
        value: { activeElement: focused ? { name: "panel-review" } : null },
      });
      return host;
    }

    /** Runs `body` on a page whose other cards take focus when `take` says so; what they were asked. */
    async function onPage(
      take: (done: ReviewDone) => boolean,
      body: () => Promise<void>,
    ): Promise<ReviewDone[]> {
      const host = globalThis as { window?: unknown };
      const saved = host.window;
      const page = new EventTarget();
      const asked: ReviewDone[] = [];
      page.addEventListener(REVIEW_DONE_EVENT, (event) => {
        const done = (event as CustomEvent<ReviewDone>).detail;
        asked.push(done);
        if (take(done)) {
          event.preventDefault();
        }
      });
      host.window = page;
      try {
        await body();
      } finally {
        host.window = saved;
      }
      return asked;
    }

    /** Runs `body` with focus lost (on the page's body), or on an element outside the card. */
    async function withDocument<T>(lost: boolean, body: () => T | Promise<T>): Promise<T> {
      const host = globalThis as { document?: unknown };
      const pageBody = { name: "body" };
      host.document = { body: pageBody, activeElement: lost ? pageBody : { name: "elsewhere" } };
      try {
        return await body();
      } finally {
        delete host.document;
      }
    }

    test("stays while it says what their decision did, and while it hands focus on", () => {
      const said = card(false) as unknown as HandOffHost;
      said._status = { icon: "mdi:check", text: STRINGS.reviewDoneMerged, tab: "review" };
      assert.match(renderText(said.render()), /Merged\. Nothing else to review\./);
      assert.ok(said.getCardSize() > 0);

      const handing = card(false) as unknown as HandOffHost;
      handing._handingOff = true;
      assert.notEqual(renderText(handing.render()), "");
      assert.ok(handing.getCardSize() > 0);
    });

    test("Merge and Keep apart record where focus goes and what to say", async () => {
      async function decide(
        reply: () => Promise<unknown>,
        marker: string,
      ): Promise<ReviewDone | null | undefined> {
        const host = card(false, [SAME_ORDER]) as unknown as HandOffHost;
        host._hass = { callWS: reply };
        const suggestion = host._snapshots.snapshot?.merge_suggestions[0];
        assert.ok(suggestion);
        const click = listener(host._renderMergeSuggestion(suggestion, 0), marker);
        assert.equal(typeof click, "function");
        (click as () => void)();
        assert.equal(host._decision?.suggestionId, "m1");
        return host._decision?.done;
      }

      // The merged parcel is the one the reply names; without it, either one.
      assert.deepEqual(await decide(async () => ({ parcel_id: "p2" }), "Merge Example Shop"), MERGED);
      assert.deepEqual(await decide(async () => ({}), "Merge Example Shop"), {
        parcels: ["p2", "p1"],
        message: STRINGS.reviewDoneMerged,
      });
      assert.deepEqual(await decide(async () => null, "apart from these parcels"), KEPT);
      const failed = await decide(async () => {
        throw new Error("Offline");
      }, "Merge Example Shop");
      assert.equal(failed, null);
    });

    test("a new decision clears what the last one said, so the card can hide after it", () => {
      const host = card(false, [SAME_ORDER]) as unknown as HandOffHost;
      host._hass = { callWS: async () => ({ parcel_id: "p2" }) };
      host._status = { icon: "mdi:check", text: STRINGS.reviewDoneKeptApart, tab: "review" };
      const suggestion = host._snapshots.snapshot?.merge_suggestions[0];
      assert.ok(suggestion);
      (listener(host._renderMergeSuggestion(suggestion, 0), "Merge Example Shop") as () => void)();
      assert.equal(host._status, null);
    });

    test("forgets a decision once its suggestion is gone while others are left", () => {
      const others = card(false, [{ ...SAME_ORDER, id: "m2" }]) as unknown as HandOffHost;
      others._decision = decided(MERGED);
      others._settleDecision();
      assert.equal(others._decision, null);

      const last = card(false) as unknown as HandOffHost;
      last._decision = decided(MERGED);
      last._settleDecision();
      assert.notEqual(last._decision, null);

      const listed = card(false, [SAME_ORDER]) as unknown as HandOffHost;
      listed._decision = decided(MERGED);
      listed._settleDecision();
      assert.notEqual(listed._decision, null);
    });

    test("starts handing focus on when its last suggestion goes while it has focus", () => {
      assert.equal(connected()._startsHandOff(), true);
      assert.equal(connected([SAME_ORDER])._startsHandOff(), false);
      assert.equal(connected([], true, true)._startsHandOff(), false);
      const hidden = connected();
      hidden.hidden = true;
      assert.equal(hidden._startsHandOff(), false);
      const handing = connected();
      handing._handingOff = true;
      assert.equal(handing._startsHandOff(), false);
      const letGo = connected();
      letGo._letGo = true;
      assert.equal(letGo._startsHandOff(), false);
      const failed = connected();
      failed.showActionError("Couldn't merge");
      assert.equal(failed._startsHandOff(), false);
      // Focus elsewhere, and no decision here.
      assert.equal(connected([], false)._startsHandOff(), false);
    });

    test("also after a decision that lost focus, not one that left it elsewhere", async () => {
      const lost = connected([], false);
      lost._decision = decided(MERGED);
      assert.equal(await withDocument(true, () => lost._startsHandOff()), true);
      const elsewhere = connected([], false);
      elsewhere._decision = decided(MERGED);
      assert.equal(await withDocument(false, () => elsewhere._startsHandOff()), false);
    });

    test("focus goes to the card that shows the decided parcel, and the card hides", async () => {
      const host = connected();
      host._handingOff = true;
      host._decision = decided(MERGED);
      const asked = await onPage(() => true, () => host._handOff());
      assert.deepEqual(asked, [MERGED]);
      assert.equal(host._handingOff, false);
      assert.equal(host._decision, null);
      assert.equal(host._status, null);
      assert.equal(host._letGo, false);
      assert.equal(renderText(host.render()), "");
    });

    test("when no card takes focus, it stays and says what happened", async () => {
      const host = connected();
      host._handingOff = true;
      host._decision = decided(KEPT);
      const asked = await onPage(() => false, () => host._handOff());
      assert.deepEqual(asked, [KEPT, { parcels: [], message: STRINGS.reviewDoneKeptApart }]);
      assert.equal(host._handingOff, false);
      assert.deepEqual(host._status, {
        icon: "mdi:check",
        text: STRINGS.reviewDoneKeptApart,
        tab: "review",
      });
      assert.match(renderText(host.render()), /Kept apart\. Nothing else to review\./);
    });

    test("without a decision here, it says only that nothing is left, or lets focus go", async () => {
      const host = connected();
      host._handingOff = true;
      const asked = await onPage(() => true, () => host._handOff());
      assert.deepEqual(asked, [{ parcels: [], message: STRINGS.reviewDoneNothing }]);
      assert.equal(host._handingOff, false);
      assert.equal(host._letGo, false);

      const alone = connected();
      alone._handingOff = true;
      await onPage(() => false, () => alone._handOff());
      assert.equal(alone._handingOff, false);
      assert.equal(alone._letGo, true);
      assert.equal(alone._status, null);
      assert.equal(renderText(alone.render()), "");
    });

    test("keeps focus when there's something to decide again, and leaves focus that moved on", async () => {
      const back = connected([SAME_ORDER]);
      back._handingOff = true;
      back._decision = decided(MERGED);
      assert.deepEqual(await onPage(() => true, () => back._handOff()), []);
      assert.equal(back._handingOff, false);
      assert.equal(back._status, null);

      const moved = connected([], false);
      moved._handingOff = true;
      moved._decision = decided(MERGED);
      const asked = await withDocument(false, () => onPage(() => true, () => moved._handOff()));
      assert.deepEqual(asked, []);
      assert.equal(moved._handingOff, false);
      assert.equal(moved._status, null);

      const removed = card(false) as unknown as HandOffHost;
      removed._handingOff = true;
      assert.deepEqual(await onPage(() => true, () => removed._handOff()), []);
      assert.equal(removed._handingOff, false);
    });
  });
});

describe("review actions", () => {
  interface ActionsHost {
    _confirmIgnore: string | null;
    _snapshots: { snapshot: Snapshot | null };
    _renderReviewActions(item: ReviewItem, busy: boolean): TemplateResult;
    _renderFilteredList(items: readonly FilteredItem[]): TemplateResult;
  }

  function actions(item: ReviewItem, confirmIgnore: string | null = null): string {
    const card = new ParcelsReviewCard() as unknown as ActionsHost;
    card._confirmIgnore = confirmIgnore;
    return renderText(card._renderReviewActions(item, false));
  }

  const MAILING: ReviewItem = {
    ...ITEM,
    sender: "news@mailing.example.com",
    sender_domain: "mailing.example.com",
    sender_org: "example.com",
  };

  test("a sender Parcels already reads can only lose this e-mail", () => {
    const html = actions({ ...MAILING, known_sender: true });
    assert.doesNotMatch(html, /Trust this sender|Ignore this sender|data-ignore/);
    // Shown as text, for phones and keyboards, and read with the button.
    assert.match(html, /aria-describedby="dismiss-hint-review-1"[^>]*> Dismiss </);
    assert.match(
      html,
      /<p class="hint" id="dismiss-hint-review-1">Remove only this e-mail. Parcels keeps reading the other e-mails from example.com.<\/p>/,
    );
    assert.doesNotMatch(html, /title="Remove only/);
  });

  test("a free mail sender is neither trusted nor ignored", () => {
    const html = actions({
      ...ITEM,
      sender: "someone@gmail.com",
      sender_domain: "gmail.com",
      sender_org: "gmail.com",
      free_mail: true,
    });
    assert.doesNotMatch(html, /Trust this sender|Ignore this sender|data-ignore|data-trust/);
    assert.match(html, /aria-describedby="dismiss-hint-review-1"[^>]*> Dismiss </);
    assert.match(
      html,
      /id="dismiss-hint-review-1">Remove only this e-mail. Anyone can send e-mail from gmail.com, so Parcels can't trust or ignore it.<\/p>/,
    );
  });

  test("another sender's Dismiss has no hint", () => {
    const html = actions(MAILING);
    assert.doesNotMatch(html, /dismiss-hint|aria-describedby/);
    assert.match(html, /data-trust/);
  });

  test("ignoring another sender asks first and says what it stops", () => {
    const asked = actions(MAILING);
    assert.match(asked, /data-ignore title="Skip e-mails from example.com from now on" aria-disabled="false" aria-expanded="false"/);
    assert.doesNotMatch(asked, /Ignore every e-mail/);

    const html = actions(MAILING, MAILING.id);
    assert.match(html, /data-ignore [^>]*aria-expanded="true"/);
    assert.match(html, /Ignore every e-mail from example.com\? Parcels stops reading its e-mails, including news/);
    assert.match(html, /class="btn danger primary" aria-disabled="false"> Ignore example.com </);
    assert.match(html, /data-ignore-cancel> Cancel </);
  });

  test("a suggestion without a number offers Edit first, not Accept", () => {
    assert.match(actions(ITEM), /class="btn primary" aria-disabled="false"> Accept </);
    assert.match(actions(ITEM), /class="btn" data-edit/);

    for (const suggestion of [
      { ...SUGGESTION, tracking_numbers: [], order_numbers: [] },
      { ...SUGGESTION, carrier: "not-a-carrier" },
    ]) {
      const html = actions({ ...ITEM, suggestion });
      assert.doesNotMatch(html, /> Accept </);
      assert.match(html, /class="btn primary" data-edit/);
    }
    const amazon = { ...SUGGESTION, tracking_numbers: [], order_numbers: [], amazon_shipment_id: "TESTSHIPMENT1" };
    assert.match(actions({ ...ITEM, suggestion: amazon }), /> Accept </);
  });

  test("ignored senders can be read again from Filtered", () => {
    const card = new ParcelsReviewCard() as unknown as ActionsHost;
    card._snapshots.snapshot = normalizeSnapshot({
      settings: { user_is_admin: true },
      ignored_senders: [{ domain: "example.net", updated: "2030-03-04T09:00:00+00:00" }],
    });
    const html = renderText(card._renderFilteredList([]));
    assert.match(html, /No filtered e-mails\./);
    assert.match(html, /<h3 class="section-label" id="ignored-senders-title">Ignored senders<\/h3>/);
    assert.match(html, /data-item-id="ignored-sender:example.net"/);
    assert.match(html, /aria-label="Stop ignoring example.net" aria-disabled="false"> Stop ignoring </);

    card._snapshots.snapshot = normalizeSnapshot({ settings: { user_is_admin: true } });
    assert.doesNotMatch(renderText(card._renderFilteredList([])), /Ignored senders/);
  });
});
