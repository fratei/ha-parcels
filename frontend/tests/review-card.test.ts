import assert from "node:assert/strict";
import { describe, test } from "node:test";

import "./dom.ts";

import type { TemplateResult } from "lit";

import { suggestionToForm, type FormProblem, type SuggestionForm } from "../src/forms.ts";
import { normalizeSnapshot } from "../src/normalize.ts";
import { ParcelsReviewCard } from "../src/review-card.ts";
import { SHOW_REVIEW_EVENT } from "../src/review-state.ts";
import type { ReviewItem, Snapshot, Suggestion } from "../src/types.ts";
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
};

const ITEM = {
  id: "review-1",
  created: "2030-03-04T09:00:00+00:00",
  received: null,
  sender: "shop@example.com",
  sender_domain: "example.com",
  subject: "Your order",
  mailbox_owner: null,
  reason: "unknown_sender",
  authenticated: true,
  trusted_sender: false,
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
