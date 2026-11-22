/** parcels-review-card: e-mails that need an administrator's decision, and the filtered ones. */
import {
  css,
  html,
  nothing,
  type CSSResultGroup,
  type PropertyDeclarations,
  type PropertyValues,
  type TemplateResult,
} from "lit";
import { live } from "lit/directives/live.js";
import { repeat } from "lit/directives/repeat.js";
import { callParcelsCommand } from "./api.ts";
import { ParcelsCardBase, focusIsLost } from "./base-card.ts";
import { CARRIER_NAMES, carrierOptions } from "./carriers.ts";
import { cardTitle, reviewCardConfig, type ReviewCardConfig } from "./config.ts";
import { parseInstant } from "./dates.ts";
import { candidateLabel, candidateLines } from "./describe.ts";
import { errorMessage } from "./errors.ts";
import { formatDateRange, formatDateTime, formatWindow } from "./format.ts";
import {
  dateProblem,
  formToSuggestion,
  suggestionToForm,
  type FormProblem,
  type SuggestionForm,
} from "./forms.ts";
import { carrierLabel, checkMeaning, kindLabel, mergeReasonLabel, noteMeaning, reasonLabel } from "./labels.ts";
import { compareLikelihood, etaRange } from "./parcels.ts";
import { defineElement, registerCard } from "./register.ts";
import {
  aiQueueText,
  filteredTitle,
  hideHandled,
  hidePending,
  senderCheckRows,
  settleHidden,
  trustResultText,
  unhide,
  withoutHidden,
  type HiddenItems,
} from "./review-state.ts";
import { KIND_LABELS, STRINGS, fmt } from "./strings.ts";
import { baseStyles } from "./styles.ts";
import type {
  FilteredItem,
  MergeSuggestion,
  Parcel,
  ReviewItem,
  SenderChecks,
  Snapshot,
  Suggestion,
  TrustResult,
} from "./types.ts";

type Tab = "review" | "filtered";

const TABS: readonly Tab[] = ["review", "filtered"];

/** Kinds that can't be accepted as a parcel; offered only when the suggestion has them. */
const UNACCEPTABLE_KINDS = new Set(["not_parcel", "unknown"]);

const EXPECTED_FORMAT: Intl.DateTimeFormatOptions = {
  weekday: "short",
  day: "numeric",
  month: "short",
};

function receivedTime(item: { received: string | null; created: string }): number {
  return parseInstant(item.received ?? item.created) ?? -Infinity;
}

function newestFirst<T extends { id: string; received: string | null; created: string }>(
  items: readonly T[],
): T[] {
  return [...items].sort(
    (a, b) => receivedTime(b) - receivedTime(a) || (a.id < b.id ? -1 : a.id > b.id ? 1 : 0),
  );
}

/** Suggestions for the latest delivery days first. */
function latestDayFirst(items: readonly MergeSuggestion[]): MergeSuggestion[] {
  return [...items].sort(
    (a, b) =>
      (b.day ?? "").localeCompare(a.day ?? "") || (a.id < b.id ? -1 : a.id > b.id ? 1 : 0),
  );
}

interface Lists {
  review: readonly ReviewItem[];
  suggestions: readonly MergeSuggestion[];
  filtered: readonly FilteredItem[];
}

function withoutKey<K, V>(map: ReadonlyMap<K, V>, key: K): ReadonlyMap<K, V> {
  if (!map.has(key)) {
    return map;
  }
  const copy = new Map(map);
  copy.delete(key);
  return copy;
}

export class ParcelsReviewCard extends ParcelsCardBase {
  static override properties: PropertyDeclarations = {
    _config: { state: true },
    _tab: { state: true },
    _editing: { state: true },
    _editForm: { state: true },
    _editProblem: { state: true },
    _busyItems: { state: true },
    _itemErrors: { state: true },
    _hidden: { state: true },
    _confirmClearAll: { state: true },
    _confirmTrust: { state: true },
    _trustStatus: { state: true },
  };

  static override styles: CSSResultGroup = [
    baseStyles,
    css`
      .tabs {
        display: flex;
        gap: 4px;
        padding: 0 12px;
        border-bottom: 1px solid var(--divider-color, rgba(0, 0, 0, 0.12));
      }
      .tab {
        min-height: 44px;
        padding: 0 12px;
        border: none;
        border-bottom: 2px solid transparent;
        background: none;
        color: var(--secondary-text-color, #727272);
        font-size: 0.875rem;
        font-weight: 500;
        cursor: pointer;
      }
      .tab:hover {
        color: var(--primary-text-color, #212121);
      }
      .tab[aria-selected="true"] {
        border-bottom-color: var(--primary-color, #03a9f4);
        color: var(--primary-color, #03a9f4);
      }
      .panel {
        padding: 12px 16px 16px;
      }
      .panel:focus-visible {
        outline-offset: -2px;
      }
      .items {
        display: flex;
        flex-direction: column;
        gap: 12px;
      }
      .item {
        padding: 12px;
        border: 1px solid var(--divider-color, rgba(0, 0, 0, 0.12));
        border-radius: 12px;
      }
      .item:focus-visible {
        outline-offset: 0;
      }
      .item-head {
        display: flex;
        flex-wrap: wrap;
        align-items: center;
        gap: 6px;
        font-size: 0.875rem;
        color: var(--secondary-text-color, #727272);
        overflow-wrap: anywhere;
      }
      .sender {
        font-weight: 500;
        color: var(--primary-text-color, #212121);
      }
      .subject {
        margin: 4px 0 0;
        font-size: 1rem;
        font-weight: 500;
        line-height: 1.35;
        overflow-wrap: anywhere;
      }
      .meta {
        margin: 4px 0 0;
        font-size: 0.8125rem;
        color: var(--secondary-text-color, #727272);
        overflow-wrap: anywhere;
      }
      .block {
        display: block;
      }
      .section-label {
        margin: 12px 0 4px;
        font-size: 0.8125rem;
        font-weight: 600;
        color: var(--secondary-text-color, #727272);
      }
      .facts {
        display: grid;
        grid-template-columns: minmax(6rem, max-content) minmax(0, 1fr);
        gap: 4px 12px;
        margin: 0;
        font-size: 0.875rem;
      }
      .facts dt {
        color: var(--secondary-text-color, #727272);
      }
      .facts dd {
        margin: 0;
        overflow-wrap: anywhere;
      }
      .facts ul {
        margin: 0;
        padding-inline-start: 18px;
      }
      .edit-form {
        display: flex;
        flex-direction: column;
        gap: 12px;
        margin-top: 12px;
      }
      .edit-form .alert {
        margin: 0;
      }
      .filtered-hint,
      .queue-hint {
        margin-bottom: 12px;
      }
      .clear-all {
        margin: 0 0 12px;
      }
      .confirm {
        margin-bottom: 12px;
        padding: 12px;
        border: 1px solid var(--divider-color, rgba(0, 0, 0, 0.12));
        border-radius: 12px;
      }
      .confirm p {
        margin: 0;
      }
      .item .confirm {
        margin: 12px 0 0;
      }
      .trust-status .alert {
        margin: 0 0 12px;
      }
      .checks {
        margin-top: 8px;
        font-size: 0.875rem;
      }
      .checks summary {
        padding: 12px 0;
        cursor: pointer;
        color: var(--secondary-text-color, #727272);
      }
      .checks .codes {
        margin: 0;
        padding-inline-start: 20px;
      }
      .candidates {
        display: flex;
        flex-direction: column;
        gap: 8px;
        margin: 8px 0 0;
        padding: 0;
        list-style: none;
      }
      .candidate {
        display: flex;
        align-items: center;
        gap: 8px;
        padding: 8px;
        border-radius: 8px;
        background: var(--secondary-background-color, rgba(0, 0, 0, 0.04));
        overflow-wrap: anywhere;
      }
      .candidate .grow {
        flex: 1;
        min-width: 0;
      }
      .subject-lines {
        margin: 4px 0 8px;
        font-size: 0.875rem;
      }
      .items-line {
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }
    `,
  ];

  /** Home Assistant keeps the card connected while it's hidden, so it can show itself again. */
  readonly connectedWhileHidden = true;

  declare private _config: ReviewCardConfig;
  declare private _tab: Tab;
  /** The review item being edited (one at a time). */
  declare private _editing: string | null;
  declare private _editForm: SuggestionForm;
  declare private _editProblem: FormProblem | null;
  /** Items with a command running. */
  declare private _busyItems: ReadonlySet<string>;
  /** The last failed command of each item. */
  declare private _itemErrors: ReadonlyMap<string, string>;
  /** Items hidden as soon as their command starts; a failed command shows them again. */
  declare private _hidden: HiddenItems<Snapshot>;
  /** True while "Clear all" waits for its confirmation. */
  declare private _confirmClearAll: boolean;
  /** The review item whose "Trust this sender" waits for its confirmation. */
  declare private _confirmTrust: string | null;
  /** What the last "Trust this sender" did. */
  declare private _trustStatus: string | null;

  /** The focused item before the current render, to move focus on when it's gone. */
  private _focusedItem: { id: string; index: number } | null = null;
  private _listCache: (Lists & { snapshot: Snapshot }) | null = null;
  private _visibleCache: { lists: Lists; hidden: HiddenItems<Snapshot>; visible: Lists } | null =
    null;
  private _clearingAll = false;

  constructor() {
    super();
    this._config = reviewCardConfig({});
    this._tab = "review";
    this._editing = null;
    this._editForm = suggestionToForm(null);
    this._editProblem = null;
    this._busyItems = new Set();
    this._itemErrors = new Map();
    this._hidden = new Map();
    this._confirmClearAll = false;
    this._confirmTrust = null;
    this._trustStatus = null;
  }

  static getStubConfig(): Record<string, unknown> {
    return {};
  }

  setConfig(config: unknown): void {
    this._config = reviewCardConfig(config);
  }

  getCardSize(): number {
    if (!this._visible()) {
      return 0;
    }
    const lists = this._visibleLists();
    if (!lists) {
      return 3;
    }
    const items =
      this._tab === "review"
        ? lists.review.length + lists.suggestions.length
        : lists.filtered.length;
    return 2 + 2 * Math.max(1, items);
  }

  getGridOptions(): Record<string, unknown> {
    return { columns: 12, rows: "auto", min_columns: 6 };
  }

  protected override hassChanged(): void {
    this._syncVisibility();
  }

  /** Only administrators see the card; before the first snapshot, their Home Assistant role decides. */
  private _visible(): boolean {
    const snapshot = this.snapshot;
    return snapshot ? snapshot.settings.user_is_admin : this.hass?.user?.is_admin === true;
  }

  private _syncVisibility(): void {
    const hidden = !this._visible();
    if (this.hidden === hidden) {
      return;
    }
    this.hidden = hidden;
    this.dispatchEvent(
      new CustomEvent("card-visibility-changed", {
        bubbles: true,
        composed: true,
        detail: { value: !hidden },
      }),
    );
  }

  private _lists(): Lists | null {
    const snapshot = this.snapshot;
    if (!snapshot) {
      return null;
    }
    if (this._listCache?.snapshot !== snapshot) {
      this._listCache = {
        snapshot,
        review: newestFirst(snapshot.review),
        suggestions: latestDayFirst(snapshot.merge_suggestions),
        filtered: newestFirst(snapshot.filtered),
      };
    }
    return this._listCache;
  }

  /** The lists as shown: without the items whose command runs or just succeeded. */
  private _visibleLists(): Lists | null {
    const lists = this._lists();
    if (!lists) {
      return null;
    }
    const hidden = this._hidden;
    if (this._visibleCache?.lists !== lists || this._visibleCache.hidden !== hidden) {
      const snapshot = this.snapshot;
      this._visibleCache = {
        lists,
        hidden,
        visible: {
          review: withoutHidden(lists.review, hidden, snapshot),
          suggestions: withoutHidden(lists.suggestions, hidden, snapshot),
          filtered: withoutHidden(lists.filtered, hidden, snapshot),
        },
      };
    }
    return this._visibleCache.visible;
  }

  /** True while the item (a review item, suggestion or filtered e-mail) is listed. */
  private _listed(itemId: string): boolean {
    const lists = this._lists();
    return lists
      ? [...lists.review, ...lists.suggestions, ...lists.filtered].some(
          (entry) => entry.id === itemId,
        )
      : false;
  }

  protected override willUpdate(changed: PropertyValues): void {
    super.willUpdate(changed);
    const active = this.shadowRoot?.activeElement;
    const item = active instanceof HTMLElement ? active.closest<HTMLElement>("[data-item-id]") : null;
    if (item) {
      const items = [...this.renderRoot.querySelectorAll<HTMLElement>("[data-item-id]")].filter(
        (element) => !element.closest("[hidden]"),
      );
      this._focusedItem = { id: item.dataset.itemId ?? "", index: items.indexOf(item) };
    } else {
      this._focusedItem = null;
    }
    // A newer snapshot shows whether the items handled before it are gone.
    this._hidden = settleHidden(this._hidden, this.snapshot);
    if (this._confirmClearAll && !this._visibleLists()?.filtered.length) {
      this._confirmClearAll = false;
      if (active instanceof HTMLElement && active.closest(".confirm")) {
        this._focusAfterUpdate("#panel-filtered");
      }
    }
    const lists = this._lists();
    if (lists) {
      // Forget the edits and errors of items that are gone.
      const ids = new Set(
        [...lists.review, ...lists.suggestions, ...lists.filtered].map((entry) => entry.id),
      );
      if (this._editing !== null && !ids.has(this._editing)) {
        this._editing = null;
        this._editProblem = null;
      }
      for (const id of this._itemErrors.keys()) {
        if (!ids.has(id)) {
          this._itemErrors = withoutKey(this._itemErrors, id);
        }
      }
    }
  }

  protected override updated(changed: PropertyValues): void {
    super.updated(changed);
    this._syncVisibility();
    const focused = this._focusedItem;
    this._focusedItem = null;
    if (!focused || this.shadowRoot?.activeElement || !focusIsLost()) {
      return;
    }
    // The focused item was handled (or re-rendered): focus it, or the one now in its place.
    const panel = this.renderRoot.querySelector<HTMLElement>(`#panel-${this._tab}`);
    const items = [...(panel?.querySelectorAll<HTMLElement>("[data-item-id]") ?? [])];
    const target =
      items.find((element) => element.dataset.itemId === focused.id) ??
      items[Math.min(Math.max(focused.index, 0), items.length - 1)] ??
      this.renderRoot.querySelector<HTMLElement>(`#tab-${this._tab}`);
    target?.focus();
  }

  protected override render(): TemplateResult | typeof nothing {
    if (!this._visible()) {
      return nothing;
    }
    const lists = this._visibleLists();
    const title = cardTitle(this._config.title, STRINGS.defaultReviewTitle);
    return html`<ha-card>
      ${title ? html`<div class="header"><h2 class="title">${title}</h2></div>` : nothing}
      ${this.renderBanners()}
      ${lists
        ? html`${this._renderTabs(
              lists.review.length + lists.suggestions.length,
              lists.filtered.length,
            )}
            <div
              class="panel"
              role="tabpanel"
              id="panel-review"
              aria-labelledby="tab-review"
              tabindex="0"
              ?hidden=${this._tab !== "review"}
            >
              ${this._renderReviewList(lists.review, lists.suggestions)}
            </div>
            <div
              class="panel"
              role="tabpanel"
              id="panel-filtered"
              aria-labelledby="tab-filtered"
              tabindex="0"
              ?hidden=${this._tab !== "filtered"}
            >
              ${this._renderFilteredList(lists.filtered)}
            </div>`
        : html`<div class="content">${this.renderLoading()}</div>`}
    </ha-card>`;
  }

  private _renderTabs(reviewCount: number, filteredCount: number): TemplateResult {
    const label = (tab: Tab): string =>
      fmt(STRINGS.tabCount, {
        label: tab === "review" ? STRINGS.tabReview : STRINGS.tabFiltered,
        count: tab === "review" ? reviewCount : filteredCount,
      });
    return html`<div
      class="tabs"
      role="tablist"
      aria-label=${STRINGS.reviewTabs}
      @keydown=${this._onTabKeyDown}
    >
      ${TABS.map((tab) => {
        const selected = this._tab === tab;
        return html`<button
          type="button"
          class="tab"
          role="tab"
          id="tab-${tab}"
          data-tab=${tab}
          aria-selected=${selected ? "true" : "false"}
          aria-controls="panel-${tab}"
          tabindex=${selected ? "0" : "-1"}
          @click=${this._onTabClick}
        >
          ${label(tab)}
        </button>`;
      })}
    </div>`;
  }

  private _renderReviewList(
    items: readonly ReviewItem[],
    suggestions: readonly MergeSuggestion[],
  ): TemplateResult {
    const settings = this.snapshot?.settings;
    const queue = settings ? aiQueueText(settings.ai_queue, settings.ai_queue_seconds) : null;
    const queueLine = queue ? html`<p class="hint queue-hint">${queue}</p>` : nothing;
    // Always rendered, so screen readers announce what "Trust this sender" did.
    const trustLine = html`<div class="trust-status" role="status">
      ${this._trustStatus
        ? html`<div class="alert">
            <ha-icon icon="mdi:shield-check-outline" aria-hidden="true"></ha-icon>
            <span class="grow">${this._trustStatus}</span>
            <button
              type="button"
              class="icon-btn"
              aria-label=${STRINGS.dismissMessage}
              title=${STRINGS.dismissMessage}
              @click=${this._dismissTrustStatus}
            >
              <ha-icon icon="mdi:close" aria-hidden="true"></ha-icon>
            </button>
          </div>`
        : nothing}
    </div>`;
    if (!items.length && !suggestions.length) {
      return html`${trustLine}${queueLine}<p class="empty">${STRINGS.emptyReview}</p>`;
    }
    return html`${trustLine}${queueLine}<div class="items">
      ${repeat(
        suggestions,
        (item) => item.id,
        (item, index) => this._renderMergeSuggestion(item, index),
      )}
      ${repeat(
        items,
        (item) => item.id,
        (item, index) => this._renderReviewItem(item, index),
      )}
    </div>`;
  }

  /** Parcels that are probably one: Merge the right candidate, or keep them all apart. */
  private _renderMergeSuggestion(suggestion: MergeSuggestion, index: number): TemplateResult {
    const locale = this.locale;
    const busy = this._busyItems.has(suggestion.id);
    const disabled = busy ? "true" : "false";
    const subjectId = `suggestion-subject-${index}`;
    const title = candidateLabel(suggestion.parcel, locale);
    const reason = mergeReasonLabel(suggestion.reason);
    const settings = this.snapshot?.settings;
    const candidates = settings
      ? [...suggestion.candidates].sort(
          compareLikelihood(suggestion.parcel, {
            today: settings.today,
            timeZone: settings.time_zone,
          }),
        )
      : suggestion.candidates;
    return html`<article
      class="item"
      tabindex="-1"
      data-item-id=${suggestion.id}
      aria-labelledby=${subjectId}
      aria-busy=${disabled}
    >
      <div class="item-head">
        <span class="badge warning">${STRINGS.possibleDuplicate}</span>
      </div>
      <h3 class="subject" id=${subjectId}>
        ${fmt(STRINGS.suggestionTitle, { parcel: candidateLines(suggestion.parcel, locale).title })}
      </h3>
      <p class="subject-lines">${this._renderLines(suggestion.parcel)}</p>
      ${reason ? html`<p class="meta">${fmt(STRINGS.reasonIs, { reason })}</p>` : nothing}
      <p class="hint">${STRINGS.suggestionHint}</p>
      <ul class="candidates">
        ${candidates.map((candidate) => {
          const label = candidateLabel(candidate, locale);
          return html`<li class="candidate">
            <span class="grow">${this._renderLines(candidate)}</span>
            <button
              type="button"
              class="btn"
              aria-label=${fmt(STRINGS.mergeSuggestedLabel, { candidate: label, title })}
              aria-disabled=${disabled}
              @click=${() =>
                this._command(suggestion.id, "suggestion/accept", {
                  suggestion_id: suggestion.id,
                  parcel_id: candidate.id,
                })}
            >
              ${STRINGS.mergeSuggested}
            </button>
          </li>`;
        })}
      </ul>
      ${this._renderError(suggestion.id)}
      <div class="row-actions">
        <button
          type="button"
          class="btn"
          aria-label=${fmt(STRINGS.keepApartLabel, { title })}
          aria-disabled=${disabled}
          @click=${() =>
            this._command(suggestion.id, "suggestion/dismiss", { suggestion_id: suggestion.id })}
        >
          ${STRINGS.keepApart}
        </button>
      </div>
    </article>`;
  }

  /** The lines that tell parcels apart: shop and status, carrier and numbers, senders, items. */
  private _renderLines(parcel: Parcel): TemplateResult {
    const lines = candidateLines(parcel, this.locale);
    return html`<span class="block"><strong>${lines.title}</strong> · ${lines.when}</span>
      <span class="meta block">${lines.carrier}</span>
      ${lines.emails ? html`<span class="meta block">${lines.emails}</span>` : nothing}
      <span class="meta block items-line">${lines.items ?? lines.noItems}</span>`;
  }

  private _renderFilteredList(items: readonly FilteredItem[]): TemplateResult {
    return html`<p class="hint filtered-hint">${STRINGS.filteredHint}</p>
      ${items.length
        ? html`${this._renderClearAll()}
            <div class="items">
            ${repeat(
              items,
              (item) => item.id,
              (item, index) => this._renderFilteredItem(item, index),
            )}
          </div>`
        : html`<p class="empty">${STRINGS.emptyFiltered}</p>`}`;
  }

  /** "Clear all", then its confirmation in place. */
  private _renderClearAll(): TemplateResult {
    if (!this._confirmClearAll) {
      return html`<div class="row-actions clear-all">
        <button type="button" class="btn" id="clear-all" @click=${this._askClearAll}>
          ${STRINGS.clearAll}
        </button>
      </div>`;
    }
    return html`<div
      class="confirm"
      role="group"
      aria-labelledby="clear-all-question"
      @keydown=${this._onConfirmKeyDown}
    >
      <p id="clear-all-question">${STRINGS.clearAllQuestion}</p>
      <div class="row-actions">
        <button type="button" class="btn danger primary" @click=${this._clearAll}>
          ${STRINGS.clearAll}
        </button>
        <button type="button" class="btn" id="clear-all-cancel" @click=${this._cancelClearAll}>
          ${STRINGS.cancel}
        </button>
      </div>
    </div>`;
  }

  private _renderHead(
    item: { sender: string; sender_domain: string; subject: string; removed?: boolean },
    subjectId: string,
    badge: TemplateResult | typeof nothing = nothing,
  ): TemplateResult {
    const title = filteredTitle({ subject: item.subject, removed: item.removed === true });
    return html`<div class="item-head">
        <span class="sender">${item.sender || item.sender_domain}</span>${badge}
      </div>
      <h3 class="subject" id=${subjectId}>${title}</h3>`;
  }

  private _renderError(itemId: string): TemplateResult | typeof nothing {
    const error = this._itemErrors.get(itemId);
    return error
      ? html`<div class="alert error" role="alert">
          <ha-icon icon="mdi:alert-circle-outline" aria-hidden="true"></ha-icon>
          <span class="grow">${error}</span>
        </div>`
      : nothing;
  }

  private _renderReviewItem(item: ReviewItem, index: number): TemplateResult {
    const locale = this.locale;
    const busy = this._busyItems.has(item.id);
    const editing = this._editing === item.id;
    const subjectId = `review-subject-${index}`;
    const received = item.received ?? item.created;
    const reason = reasonLabel(item.reason);
    const meta = [
      received ? fmt(STRINGS.receivedOn, { date: formatDateTime(received, locale) }) : "",
      item.mailbox_owner ? fmt(STRINGS.mailboxOf, { owner: item.mailbox_owner }) : "",
      reason ? fmt(STRINGS.reasonIs, { reason }) : "",
    ].filter(Boolean);
    const badge =
      item.source === "ai"
        ? html`<span class="badge ai" title=${STRINGS.aiSuggestionLabel}>
            ${STRINGS.aiBadge}<span class="sr-only">, ${STRINGS.aiSuggestionLabel}</span>
          </span>`
        : nothing;
    return html`<article
      class="item"
      tabindex="-1"
      data-item-id=${item.id}
      aria-labelledby=${subjectId}
      aria-busy=${busy ? "true" : "false"}
    >
      ${this._renderHead(item, subjectId, badge)}
      ${meta.length ? html`<p class="meta">${meta.join(" · ")}</p>` : nothing}
      ${item.authenticated
        ? nothing
        : html`<div class="alert warning">
            <ha-icon icon="mdi:shield-alert-outline" aria-hidden="true"></ha-icon>
            <span class="grow">
              <strong class="block">${STRINGS.unverifiedSender}</strong>
              ${item.trusted_sender
                ? fmt(STRINGS.trustedSenderNote, { domain: item.sender_domain || item.sender })
                : STRINGS.unverifiedSenderHint}
            </span>
          </div>`}
      ${item.checks ? this._renderChecks(item.checks) : nothing}
      ${item.errors.length ? this._renderFailedChecks(item.errors) : nothing}
      ${item.notes.length ? this._renderNotes(item.notes) : nothing}
      ${editing ? this._renderEditForm(item, busy) : this._renderSuggestion(item.suggestion)}
      ${this._renderError(item.id)} ${editing ? nothing : this._renderReviewActions(item, busy)}
    </article>`;
  }

  /** How the sender checks went: the headers, the servers that wrote them and the results. */
  private _renderChecks(checks: SenderChecks): TemplateResult {
    return html`<details class="checks">
      <summary>${STRINGS.senderChecks}</summary>
      <dl class="facts">
        ${senderCheckRows(checks).map(([label, value]) => html`<dt>${label}</dt><dd>${value}</dd>`)}
      </dl>
    </details>`;
  }

  /** The checks a rejected AI answer failed, as the validator's codes. */
  private _renderFailedChecks(errors: string[]): TemplateResult {
    return html`<details class="checks">
      <summary>${STRINGS.failedChecks}</summary>
      <ul class="codes">
        ${errors.map((code) => {
          const meaning = checkMeaning(code);
          return html`<li><code>${code}</code>${meaning ? `: ${meaning}` : nothing}</li>`;
        })}
      </ul>
    </details>`;
  }

  /** What the checks changed in an AI answer: notes for administrators, not failures. */
  private _renderNotes(notes: string[]): TemplateResult {
    return html`<details class="checks">
      <summary>${STRINGS.aiNotes}</summary>
      <p class="hint">${STRINGS.aiNotesHint}</p>
      <ul class="codes">
        ${notes.map((code) => {
          const meaning = noteMeaning(code);
          return html`<li><code>${code}</code>${meaning ? `: ${meaning}` : nothing}</li>`;
        })}
      </ul>
    </details>`;
  }

  private _renderSuggestion(suggestion: Suggestion | null): TemplateResult {
    if (!suggestion) {
      return html`<p class="hint section-label">${STRINGS.noSuggestion}</p>`;
    }
    const locale = this.locale;
    const eta = etaRange(suggestion);
    const rows: Array<[string, string | TemplateResult | null]> = [
      [STRINGS.fieldKind, kindLabel(suggestion.kind) || null],
      [STRINGS.fieldMerchant, suggestion.merchant],
      [STRINGS.fieldCarrier, carrierLabel({ carrier: suggestion.carrier, carrier_name: null })],
      [STRINGS.fieldTrackingNumbers, suggestion.tracking_numbers.join(", ") || null],
      [STRINGS.fieldOrderNumbers, suggestion.order_numbers.join(", ") || null],
      [STRINGS.fieldReference, suggestion.reference],
      [
        suggestion.kind === "customer_return" ? STRINGS.pickup : STRINGS.expected,
        eta ? formatDateRange(eta.start, eta.end, locale, EXPECTED_FORMAT) : null,
      ],
      [STRINGS.timeWindow, formatWindow(suggestion.window_start, suggestion.window_end, locale)],
      [STRINGS.pickupPoint, suggestion.pickup_point],
      [STRINGS.pickupCode, suggestion.pickup_code],
      [
        STRINGS.items,
        suggestion.items.length
          ? html`<ul>
              ${suggestion.items.map((entry) => html`<li>${entry}</li>`)}
            </ul>`
          : null,
      ],
    ];
    return html`<p class="section-label">${STRINGS.suggestion}</p>
      <dl class="facts">
        ${rows
          .filter(([, value]) => value !== null && value !== "")
          .map(([label, value]) => html`<dt>${label}</dt><dd>${value}</dd>`)}
      </dl>`;
  }

  private _renderReviewActions(item: ReviewItem, busy: boolean): TemplateResult {
    const disabled = busy ? "true" : "false";
    const domain = item.sender_domain || item.sender;
    return html`<div class="row-actions">
      ${item.suggestion
        ? html`<button
            type="button"
            class="btn primary"
            aria-disabled=${disabled}
            @click=${() => this._accept(item)}
          >
            ${STRINGS.accept}
          </button>`
        : nothing}
      <button
        type="button"
        class="btn"
        data-edit
        aria-disabled=${disabled}
        @click=${() => this._startEdit(item)}
      >
        ${STRINGS.edit}
      </button>
      <button
        type="button"
        class="btn"
        aria-disabled=${disabled}
        @click=${() => this._command(item.id, "review/dismiss", { review_id: item.id })}
      >
        ${STRINGS.dismiss}
      </button>
      ${item.trusted_sender || item.fill
        ? nothing
        : html`<button
            type="button"
            class="btn"
            data-trust
            title=${fmt(STRINGS.trustSenderHint, { domain })}
            aria-disabled=${disabled}
            aria-expanded=${item.authenticated
              ? nothing
              : this._confirmTrust === item.id
                ? "true"
                : "false"}
            @click=${() => this._askTrust(item)}
          >
            ${STRINGS.trustSender}
          </button>`}
      <button
        type="button"
        class="btn danger"
        title=${fmt(STRINGS.ignoreSenderHint, { domain })}
        aria-disabled=${disabled}
        @click=${() => this._command(item.id, "review/ignore_sender", { review_id: item.id })}
      >
        ${STRINGS.ignoreSender}
      </button>
    </div>
    ${this._confirmTrust === item.id ? this._renderTrustConfirm(item, domain, busy) : nothing}`;
  }

  /** The confirmation of "Trust this sender" for an e-mail that failed the sender checks. */
  private _renderTrustConfirm(item: ReviewItem, domain: string, busy: boolean): TemplateResult {
    const questionId = `trust-question-${item.id}`;
    return html`<div
      class="confirm"
      role="group"
      aria-labelledby=${questionId}
      @keydown=${(event: KeyboardEvent) => this._onTrustKeyDown(event, item.id)}
    >
      <p id=${questionId}>${fmt(STRINGS.trustQuestion, { domain })}</p>
      <div class="row-actions">
        <button
          type="button"
          class="btn danger primary"
          aria-disabled=${busy ? "true" : "false"}
          @click=${() => void this._trust(item)}
        >
          ${fmt(STRINGS.trustConfirm, { domain })}
        </button>
        <button type="button" class="btn" data-trust-cancel @click=${() => this._cancelTrust(item.id)}>
          ${STRINGS.cancel}
        </button>
      </div>
    </div>`;
  }

  private _renderEditForm(item: ReviewItem, busy: boolean): TemplateResult {
    const form = this._editForm;
    const problem = this._editProblem;
    const kinds = Object.keys(KIND_LABELS).filter(
      (kind) => !UNACCEPTABLE_KINDS.has(kind) || kind === form.kind,
    );
    if (!kinds.includes(form.kind)) {
      kinds.unshift(form.kind);
    }
    const carriers = carrierOptions();
    if (form.carrier && !Object.hasOwn(CARRIER_NAMES, form.carrier)) {
      carriers.unshift({ id: form.carrier, name: form.carrier });
    }
    const text = (
      name: keyof SuggestionForm,
      label: string,
      type: "text" | "date" | "time" = "text",
      hintId?: string,
    ): TemplateResult => {
      const invalid = problem?.field === name;
      const describedBy = [invalid ? "edit-error" : "", hintId ?? ""].filter(Boolean).join(" ");
      return html`<label class="field">
        <span class="field-label">${label}</span>
        <input
          type=${type}
          name=${name}
          autocomplete="off"
          .value=${live(form[name])}
          aria-invalid=${invalid ? "true" : "false"}
          aria-describedby=${describedBy || nothing}
          @input=${this._onEditInput}
        />
      </label>`;
    };
    return html`<form id="edit-form" class="edit-form" novalidate @submit=${this._submitEdit}>
      <div class="form-grid">
        <label class="field">
          <span class="field-label">${STRINGS.fieldKind}</span>
          <select name="kind" data-first @change=${this._onEditInput}>
            ${kinds.map(
              (kind) =>
                html`<option value=${kind} ?selected=${kind === form.kind}>
                  ${kindLabel(kind) || kind}
                </option>`,
            )}
          </select>
        </label>
        ${text("merchant", STRINGS.fieldMerchant)}
        <label class="field">
          <span class="field-label">${STRINGS.fieldCarrier}</span>
          <select name="carrier" @change=${this._onEditInput}>
            <option value="" ?selected=${form.carrier === ""}>${STRINGS.carrierUnknown}</option>
            ${carriers.map(
              (carrier) =>
                html`<option value=${carrier.id} ?selected=${carrier.id === form.carrier}>
                  ${carrier.name}
                </option>`,
            )}
          </select>
        </label>
        <div class="field">
          ${text("tracking_numbers", STRINGS.fieldTrackingNumbers, "text", "edit-hint-tracking")}
          <p class="hint" id="edit-hint-tracking">${STRINGS.hintList}</p>
        </div>
        <div class="field">
          ${text("order_numbers", STRINGS.fieldOrderNumbers, "text", "edit-hint-orders")}
          <p class="hint" id="edit-hint-orders">${STRINGS.hintList}</p>
        </div>
        ${text("reference", STRINGS.fieldReference)}
        ${text("eta_start", STRINGS.fieldEtaStart, "date")}
        ${text("eta_end", STRINGS.fieldEtaEnd, "date")}
        ${text("window_start", STRINGS.fieldWindowStart, "time")}
        ${text("window_end", STRINGS.fieldWindowEnd, "time")}
        ${text("pickup_point", STRINGS.fieldPickupPoint)}
        ${text("pickup_code", STRINGS.fieldPickupCode)}
        <label class="field wide">
          <span class="field-label">${STRINGS.fieldItems}</span>
          <textarea
            name="items"
            rows="3"
            .value=${live(form.items)}
            aria-describedby="edit-hint-items"
            @input=${this._onEditInput}
          ></textarea>
          <span class="hint" id="edit-hint-items">${STRINGS.hintItems}</span>
        </label>
      </div>
      ${problem
        ? html`<div class="alert error" id="edit-error" role="alert">
            <span class="grow">${problem.message}</span>
          </div>`
        : nothing}
      <div class="row-actions">
        <button type="submit" class="btn primary" aria-disabled=${busy ? "true" : "false"}>
          ${STRINGS.acceptWithChanges}
        </button>
        <button type="button" class="btn" @click=${() => this._cancelEdit(item.id)}>
          ${STRINGS.cancel}
        </button>
      </div>
    </form>`;
  }

  private _renderFilteredItem(item: FilteredItem, index: number): TemplateResult {
    const subjectId = `filtered-subject-${index}`;
    const received = item.received ?? item.created;
    const busy = this._busyItems.has(item.id);
    return html`<article
      class="item"
      tabindex="-1"
      data-item-id=${item.id}
      aria-labelledby=${subjectId}
      aria-busy=${busy ? "true" : "false"}
    >
      ${this._renderHead(item, subjectId)}
      ${received
        ? html`<p class="meta">
            ${fmt(STRINGS.receivedOn, { date: formatDateTime(received, this.locale) })}
          </p>`
        : nothing}
      ${this._renderError(item.id)}
      <div class="row-actions">
        <button
          type="button"
          class="btn"
          aria-disabled=${busy ? "true" : "false"}
          @click=${() => this._command(item.id, "review/restore", { filtered_id: item.id })}
        >
          ${STRINGS.restore}
        </button>
        <button
          type="button"
          class="btn"
          title=${STRINGS.clearHint}
          aria-disabled=${busy ? "true" : "false"}
          @click=${() => this._command(item.id, "filtered/clear", { filtered_id: item.id })}
        >
          ${STRINGS.clear}
        </button>
      </div>
    </article>`;
  }

  private _selectTab(tab: Tab, focus: boolean): void {
    this._tab = tab;
    if (focus) {
      void this.updateComplete.then(() =>
        this.renderRoot.querySelector<HTMLElement>(`#tab-${tab}`)?.focus(),
      );
    }
  }

  private _onTabClick(event: MouseEvent): void {
    const tab = (event.currentTarget as HTMLElement).dataset.tab as Tab;
    this._selectTab(tab, false);
  }

  private _onTabKeyDown(event: KeyboardEvent): void {
    const current = TABS.indexOf(this._tab);
    const rtl = getComputedStyle(event.currentTarget as HTMLElement).direction === "rtl";
    let next: number;
    switch (event.key) {
      case "ArrowRight":
        next = current + (rtl ? -1 : 1);
        break;
      case "ArrowLeft":
        next = current + (rtl ? 1 : -1);
        break;
      case "Home":
        next = 0;
        break;
      case "End":
        next = TABS.length - 1;
        break;
      default:
        return;
    }
    event.preventDefault();
    const tab = TABS[(next + TABS.length) % TABS.length];
    if (tab) {
      this._selectTab(tab, true);
    }
  }

  private _focusAfterUpdate(selector: string): void {
    void this.updateComplete.then(() =>
      this.renderRoot.querySelector<HTMLElement>(selector)?.focus(),
    );
  }

  private _askClearAll(): void {
    this._confirmClearAll = true;
    this._focusAfterUpdate("#clear-all-cancel");
  }

  private _cancelClearAll(): void {
    this._confirmClearAll = false;
    this._focusAfterUpdate("#clear-all");
  }

  private _onConfirmKeyDown(event: KeyboardEvent): void {
    if (event.key === "Escape") {
      event.preventDefault();
      event.stopPropagation();
      this._cancelClearAll();
    }
  }

  /** Clears every filtered e-mail shown; they disappear at once and come back if that fails. */
  private async _clearAll(): Promise<void> {
    const hass = this.hass;
    const itemIds = this._visibleLists()?.filtered.map((item) => item.id) ?? [];
    if (!hass || this._clearingAll || !itemIds.length) {
      return;
    }
    this._clearingAll = true;
    this._confirmClearAll = false;
    this._hidden = hidePending(this._hidden, itemIds);
    this._focusAfterUpdate("#panel-filtered");
    try {
      await callParcelsCommand(hass, "filtered/clear_all");
      this._hidden = hideHandled(this._hidden, itemIds, this.snapshot, (itemId) =>
        this._listed(itemId),
      );
    } catch (error) {
      this._hidden = unhide(this._hidden, itemIds);
      this.showActionError(fmt(STRINGS.actionFailed, { message: errorMessage(error) }));
    } finally {
      this._clearingAll = false;
    }
  }

  private _focusInItem(itemId: string, selector: string): void {
    void this.updateComplete.then(() => {
      const item = this.renderRoot.querySelector<HTMLElement>(
        `[data-item-id="${CSS.escape(itemId)}"]`,
      );
      (item?.querySelector<HTMLElement>(selector) ?? item)?.focus();
    });
  }

  private _startEdit(item: ReviewItem): void {
    if (this._busyItems.has(item.id)) {
      return;
    }
    this._editing = item.id;
    this._editForm = suggestionToForm(item.suggestion);
    this._editProblem = null;
    this._itemErrors = withoutKey(this._itemErrors, item.id);
    this._focusInItem(item.id, "[data-first]");
  }

  private _cancelEdit(itemId: string): void {
    this._editing = null;
    this._editProblem = null;
    this._focusInItem(itemId, "[data-edit]");
  }

  private _onEditInput(event: Event): void {
    const input = event.currentTarget as HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement;
    const name = input.name as keyof SuggestionForm;
    this._editForm = { ...this._editForm, [name]: input.value };
    this._editProblem = null;
  }

  private _submitEdit(event: Event): void {
    event.preventDefault();
    const itemId = this._editing;
    if (itemId === null || this._busyItems.has(itemId)) {
      return;
    }
    const problem = dateProblem(this._editForm);
    if (problem) {
      this._editProblem = problem;
      this._focusInItem(itemId, `[name="${problem.field}"]`);
      return;
    }
    void this._command(
      itemId,
      "review/accept",
      { review_id: itemId, overrides: formToSuggestion(this._editForm) },
      {
        onSuccess: () => {
          if (this._editing === itemId) {
            this._editing = null;
          }
        },
      },
    );
  }

  private _accept(item: ReviewItem): void {
    void this._command(item.id, "review/accept", { review_id: item.id });
  }

  /** Trusts the sender at once when the e-mail passed the checks; otherwise asks first. */
  private _askTrust(item: ReviewItem): void {
    if (this._busyItems.has(item.id)) {
      return;
    }
    if (item.authenticated) {
      void this._trust(item);
      return;
    }
    this._confirmTrust = item.id;
    this._focusInItem(item.id, "[data-trust-cancel]");
  }

  private _cancelTrust(itemId: string): void {
    this._confirmTrust = null;
    this._focusInItem(itemId, "[data-trust]");
  }

  private _onTrustKeyDown(event: KeyboardEvent, itemId: string): void {
    if (event.key === "Escape") {
      event.preventDefault();
      event.stopPropagation();
      this._cancelTrust(itemId);
    }
  }

  private async _trust(item: ReviewItem): Promise<void> {
    const domain = item.sender_domain || item.sender;
    this._confirmTrust = null;
    this._trustStatus = null;
    this._focusInItem(item.id, "[data-trust]");
    await this._command(
      item.id,
      "review/trust_sender",
      { review_id: item.id },
      {
        // The item stays until the next list: its e-mail is added or read again.
        hide: false,
        onSuccess: (result) => {
          const done = (result ?? {}) as Partial<TrustResult>;
          this._trustStatus = trustResultText({
            domain: done.domain ?? domain,
            added: done.added ?? 0,
            rechecking: done.rechecking ?? 0,
            kept: done.kept ?? 0,
          });
        },
      },
    );
  }

  private _dismissTrustStatus(): void {
    this._trustStatus = null;
  }

  /**
   * Sends a review command for one item. The item disappears at once (unless `hide` is false),
   * so the next one can be used; if the command fails, it comes back with the error, or the
   * error shows on the card once the item is gone.
   */
  private async _command(
    itemId: string,
    command: string,
    data: Record<string, unknown>,
    { hide = true, onSuccess }: { hide?: boolean; onSuccess?: (result: unknown) => void } = {},
  ): Promise<void> {
    const hass = this.hass;
    if (!hass || this._busyItems.has(itemId) || this._hidden.has(itemId)) {
      return;
    }
    this._busyItems = new Set([...this._busyItems, itemId]);
    this._itemErrors = withoutKey(this._itemErrors, itemId);
    if (hide) {
      this._hidden = hidePending(this._hidden, [itemId]);
    }
    try {
      const result = await callParcelsCommand<unknown>(hass, command, data);
      if (hide) {
        this._hidden = hideHandled(this._hidden, [itemId], this.snapshot, (id) =>
          this._listed(id),
        );
      }
      onSuccess?.(result);
    } catch (error) {
      this._hidden = unhide(this._hidden, [itemId]);
      const message = fmt(STRINGS.actionFailed, { message: errorMessage(error) });
      if (this._listed(itemId)) {
        this._itemErrors = new Map([...this._itemErrors, [itemId, message]]);
      } else {
        this.showActionError(message);
      }
    } finally {
      const busy = new Set(this._busyItems);
      busy.delete(itemId);
      this._busyItems = busy;
    }
  }
}

defineElement("parcels-review-card", ParcelsReviewCard);
registerCard("parcels-review-card", STRINGS.reviewCardName, STRINGS.reviewCardDescription);

declare global {
  interface HTMLElementTagNameMap {
    "parcels-review-card": ParcelsReviewCard;
  }
}
