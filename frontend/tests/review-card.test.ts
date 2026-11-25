import assert from "node:assert/strict";
import { describe, test } from "node:test";

import "./dom.ts";

import type { TemplateResult } from "lit";

import { suggestionToForm, type FormProblem, type SuggestionForm } from "../src/forms.ts";
import { ParcelsReviewCard } from "../src/review-card.ts";
import type { ReviewItem, Suggestion } from "../src/types.ts";
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
