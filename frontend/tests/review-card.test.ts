import assert from "node:assert/strict";
import { describe, test } from "node:test";

import "./dom.ts";

import type { TemplateResult } from "lit";

import { suggestionToForm, type FormProblem, type SuggestionForm } from "../src/forms.ts";
import { normalizeSnapshot } from "../src/normalize.ts";
import { ParcelsReviewCard } from "../src/review-card.ts";
import { SHOW_REVIEW_EVENT } from "../src/review-state.ts";
import type { FilteredItem, ReviewItem, Snapshot, Suggestion } from "../src/types.ts";
import { renderText } from "./render.ts";

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
