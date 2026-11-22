/** The parcel details dialog shared by the week and list cards. */
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
import { styleMap } from "lit/directives/style-map.js";
import { callParcelsCommand, callParcelsService, callParcelsServiceForParcel } from "./api.ts";
import { canCheckAgain, checkAgainText, normalizeCheckAgain } from "./check-again.ts";
import { parseInstant } from "./dates.ts";
import { candidateLabel, candidateLines, couldAlsoBe } from "./describe.ts";
import { ParcelsDialogBase, OPEN_RETURN_EVENT, type ReturnFocus } from "./dialog-base.ts";
import { errorMessage } from "./errors.ts";
import {
  collectByFact,
  deliveredFact,
  EXPECTED_FORMAT,
  nextAttemptFact,
  statusFact,
} from "./facts.ts";
import {
  formatDate,
  formatDateRange,
  formatDateTime,
  formatDayWithoutTime,
  formatWindow,
  localeOptions,
  MEDIUM_DATE,
  type LocaleOptions,
} from "./format.ts";
import {
  dateFormToUpdate,
  dateProblem,
  isValidSplit,
  parcelToDateForm,
  type DateForm,
  type FormProblem,
} from "./forms.ts";
import { shipmentPackages } from "./groups.ts";
import {
  carrierLabel,
  etaSourceLabel,
  inferredNotice,
  mergeReasonLabel,
  parcelAppName,
  parcelTitle,
  sourceLabel,
  statusLabel,
} from "./labels.ts";
import { normalizeDetails } from "./normalize.ts";
import {
  originEntries,
  originRows,
  originsTitle,
  restoreOutcome,
  rowIds,
  splitBlockedReason,
  type OriginEntry,
  type OriginRow,
  type RestoreOutcome,
} from "./origins.ts";
import {
  alsoPossible,
  etaRange,
  possibleHint,
  possibleMatches,
  rankMergeCandidates,
  rankPossible,
  searchCandidates,
  type DayContext,
  type MergeCandidates,
  type PossibleMatch,
} from "./parcels.ts";
import { defineElement } from "./register.ts";
import { RETURN_ICON, returnState, returnsOfParcel } from "./returns.ts";
import { isActiveStatus, statusColor } from "./status.ts";
import { STRINGS, fmt } from "./strings.ts";
import { baseStyles, dialogStyles } from "./styles.ts";
import { safeHttpsUrl } from "./url.ts";
import type { CustomerReturn, Parcel, ParcelDetails, Snapshot, TimelineEntry } from "./types.ts";

type Mode = "view" | "date" | "merge" | "split" | "archive";
type CopyState = "idle" | "copied" | "failed";

const RESTORE_NOTICES: Record<RestoreOutcome["notice"], string> = {
  restored: STRINGS.restoredNotice,
  elsewhere: STRINGS.restoredElsewhereNotice,
  review: STRINGS.restoredReviewNotice,
  noParcel: STRINGS.restoredNoParcelNotice,
};

/** What a row action of the "E-mails" section did. */
interface OriginNotice {
  text: string;
  /** Takes the action back; null when it can't be. */
  undo: (() => void) | null;
  /** A parcel the notice can show. */
  show: string | null;
}

const EMPTY_DATE_FORM: DateForm = { eta_start: "", eta_end: "", window_start: "", window_end: "" };
/** The merge picker gets a search field above this many candidates. */
const SEARCH_FROM = 6;

function newestFirst(entries: readonly TimelineEntry[]): TimelineEntry[] {
  return entries
    .map((entry, index) => ({ entry, index, time: parseInstant(entry.time) ?? -Infinity }))
    .sort((a, b) => b.time - a.time || b.index - a.index)
    .map(({ entry }) => entry);
}

export class ParcelsDetailsDialog extends ParcelsDialogBase {
  static override properties: PropertyDeclarations = {
    snapshot: { attribute: false },
    locale: { attribute: false },
    _parcelId: { state: true },
    _details: { state: true },
    _loading: { state: true },
    _loadError: { state: true },
    _mode: { state: true },
    _copyState: { state: true },
    _dateForm: { state: true },
    _formError: { state: true },
    _mergeTarget: { state: true },
    _mergeQuery: { state: true },
    _mergeOlder: { state: true },
    _mergeHint: { state: true },
    _splitSelection: { state: true },
    _pendingPrivate: { state: true },
    _checking: { state: true },
    _checkStatus: { state: true },
    _originsOpen: { state: true },
    _openFolds: { state: true },
    _originNotice: { state: true },
  };

  static override styles: CSSResultGroup = [
    baseStyles,
    dialogStyles,
    css`
      .merge-list {
        display: flex;
        flex-direction: column;
        gap: 6px;
        min-width: 0;
        margin: 8px 0 0;
        padding: 0;
        border: 0;
      }
      .merge-option {
        display: flex;
        align-items: flex-start;
        gap: 10px;
        padding: 8px 10px;
        border: 1px solid var(--divider-color, #e0e0e0);
        border-radius: 8px;
        cursor: pointer;
      }
      .merge-option:has(input:checked) {
        border-color: var(--primary-color, #03a9f4);
        box-shadow: inset 0 0 0 1px var(--primary-color, #03a9f4);
      }
      .merge-option input {
        flex: none;
        width: 18px;
        height: 18px;
        margin: 1px 0 0;
        accent-color: var(--primary-color, #03a9f4);
      }
      .merge-lines {
        display: flex;
        flex-direction: column;
        gap: 2px;
        min-width: 0;
        font-size: 0.875rem;
      }
      .merge-line {
        overflow-wrap: anywhere;
      }
      .merge-line.items {
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }
      .merge-hint {
        color: var(--error-color, #db4437);
      }
      .possible-list {
        display: flex;
        flex-direction: column;
        gap: 6px;
        margin: 8px 0 0;
        padding: 0;
        list-style: none;
      }
      .possible-item {
        display: flex;
        flex-wrap: wrap;
        align-items: center;
        gap: 8px;
        padding: 8px 10px;
        border: 1px solid var(--divider-color, #e0e0e0);
        border-radius: 8px;
      }
      .possible-item .merge-lines {
        flex: 1 1 12rem;
      }
      .possible-actions {
        display: flex;
        flex-wrap: wrap;
        gap: 6px;
      }
      .facts {
        display: flex;
        flex-direction: column;
        gap: 8px;
        margin: 8px 0 0;
      }
      .facts > div {
        display: grid;
        grid-template-columns: minmax(6rem, 32%) minmax(0, 1fr);
        gap: 12px;
        align-items: baseline;
      }
      .facts dt {
        color: var(--secondary-text-color, #727272);
        font-size: 0.875rem;
      }
      .facts dd {
        margin: 0;
        overflow-wrap: anywhere;
      }
      .facts ul {
        margin: 0;
        padding-inline-start: 18px;
      }
      .link {
        display: inline-flex;
        align-items: center;
        gap: 4px;
        margin-inline-start: 8px;
        --mdc-icon-size: 16px;
      }
      .copy-row {
        display: flex;
        flex-wrap: wrap;
        align-items: center;
        gap: 8px;
      }
      .copy-row input {
        flex: 1 1 12rem;
        width: auto;
        min-width: 0;
        font-family: var(--code-font-family, monospace);
      }
      .copy-status:empty {
        display: none;
      }
      .copy-status {
        flex-basis: 100%;
      }
      .switch-row {
        margin-top: 12px;
      }
      .origins > summary {
        cursor: pointer;
      }
      .origins > .hint {
        margin-bottom: 8px;
      }
      .origin-list {
        display: flex;
        flex-direction: column;
        gap: 6px;
        margin: 0;
        padding: 0;
        list-style: none;
      }
      .origin-list .origin-list {
        margin-top: 6px;
      }
      .origin {
        display: flex;
        flex-direction: column;
        gap: 2px;
        min-width: 0;
        padding: 8px 10px;
        border: 1px solid var(--divider-color, #e0e0e0);
        border-radius: 8px;
        font-size: 0.875rem;
      }
      .origin .row-actions {
        margin-top: 6px;
      }
      .origin-line {
        overflow-wrap: anywhere;
      }
      .origin-items {
        margin: 2px 0 0;
        padding-inline-start: 18px;
        overflow-wrap: anywhere;
      }
      span.origin-items {
        display: flex;
        flex-direction: column;
        padding-inline-start: 0;
      }
      .fold-toggle {
        display: inline-flex;
        align-items: center;
        gap: 2px;
        padding-inline-start: 0;
        text-align: start;
        --mdc-icon-size: 18px;
      }
      .split-list {
        display: flex;
        flex-direction: column;
        gap: 6px;
      }
      .split-row {
        align-items: flex-start;
        padding: 8px 10px;
        border: 1px solid var(--divider-color, #e0e0e0);
        border-radius: 8px;
      }
      .split-row input {
        flex: none;
        width: 18px;
        height: 18px;
        margin: 1px 0 0;
      }
      .origin-body {
        display: flex;
        flex-direction: column;
        gap: 2px;
        min-width: 0;
        font-size: 0.875rem;
      }
      .timeline {
        margin: 0;
        padding: 0;
        list-style: none;
      }
      .timeline li {
        position: relative;
        padding: 0 0 12px 22px;
      }
      .timeline li::before {
        content: "";
        position: absolute;
        inset-inline-start: 5px;
        top: 14px;
        bottom: 0;
        border-inline-start: 2px solid var(--divider-color, rgba(0, 0, 0, 0.12));
      }
      .timeline li:last-child::before {
        display: none;
      }
      .timeline .dot {
        position: absolute;
        inset-inline-start: 0;
        top: 4px;
        width: 12px;
        height: 12px;
        border-radius: 50%;
        background: var(--dot-color);
      }
      .timeline .entry-title {
        font-weight: 500;
      }
      .timeline .entry-meta {
        font-size: 0.8125rem;
        color: var(--secondary-text-color, #727272);
      }
      fieldset {
        margin: 0;
        padding: 0;
        border: none;
      }
      legend {
        margin-bottom: 8px;
        padding: 0;
      }
    `,
  ];

  /** The latest snapshot, from the card. */
  declare snapshot: Snapshot | null;
  declare locale: LocaleOptions;
  declare private _parcelId: string | null;
  declare private _details: ParcelDetails | null;
  declare private _loading: boolean;
  declare private _loadError: string | null;
  declare private _mode: Mode;
  declare private _copyState: CopyState;
  declare private _dateForm: DateForm;
  /** The validation problem of the date form. */
  declare private _formError: FormProblem | null;
  declare private _mergeTarget: string;
  declare private _mergeQuery: string;
  /** Whether the merge picker shows archived and long-closed parcels. */
  declare private _mergeOlder: boolean;
  /** Merge was pressed before a parcel was chosen. */
  declare private _mergeHint: boolean;
  declare private _splitSelection: readonly string[];
  /** The private value just chosen, until the next snapshot. */
  declare private _pendingPrivate: boolean | null;
  /** "Check again" is running. */
  declare private _checking: boolean;
  /** What "Check again" did, until another parcel is shown. */
  declare private _checkStatus: string | null;
  /** The "E-mails" section is open. */
  declare private _originsOpen: boolean;
  /** The folds of repeated e-mails that are open, by key. */
  declare private _openFolds: ReadonlySet<string>;
  /** What a row action did, until another parcel is shown. */
  declare private _originNotice: OriginNotice | null;

  /** Counts loads, so that only the latest result is shown. */
  private _request = 0;
  /** Counts "Check again" runs, so that a late one doesn't end a newer one. */
  private _checkRun = 0;
  /** The snapshot parcel the details were loaded for. */
  private _loadedKey = "";
  /** The rows of the "E-mails" section, for the details and locale they were made from. */
  private _rowsCache: { details: ParcelDetails; locale: LocaleOptions; rows: OriginRow[] } | null = null;

  constructor() {
    super();
    this.snapshot = null;
    this.locale = localeOptions(undefined);
    this._parcelId = null;
    this._details = null;
    this._loading = false;
    this._loadError = null;
    this._mode = "view";
    this._copyState = "idle";
    this._dateForm = EMPTY_DATE_FORM;
    this._formError = null;
    this._mergeTarget = "";
    this._mergeQuery = "";
    this._mergeOlder = false;
    this._mergeHint = false;
    this._splitSelection = [];
    this._pendingPrivate = null;
    this._checking = false;
    this._checkStatus = null;
    this._originsOpen = false;
    this._openFolds = new Set();
    this._originNotice = null;
  }

  /** Opens the dialog for a parcel; `returnFocus` runs when it closes. */
  async open(parcelId: string, returnFocus: ReturnFocus | null = null): Promise<void> {
    this._parcelId = parcelId;
    this._details = null;
    this._loadError = null;
    this._mode = "view";
    this._copyState = "idle";
    this._formError = null;
    this._pendingPrivate = null;
    this._checkRun += 1;
    this._checking = false;
    this._checkStatus = null;
    this._resetOrigins();
    void this._load();
    await this.showDialog(returnFocus);
  }

  /** Shows another package of the same shipment in the open dialog. */
  private _switchTo(parcelId: string): void {
    if (this._busy || parcelId === this._parcelId) {
      return;
    }
    this._parcelId = parcelId;
    this._details = null;
    this._loadError = null;
    this._error = null;
    this._mode = "view";
    this._copyState = "idle";
    this._formError = null;
    this._pendingPrivate = null;
    this._checkStatus = null;
    this._resetOrigins();
    void this._load();
    void this.focusAfterRender("[data-current-package]");
  }

  /** Another parcel is shown: its "E-mails" section starts closed, without a notice. */
  private _resetOrigins(): void {
    this._originsOpen = false;
    this._openFolds = new Set();
    this._originNotice = null;
  }

  protected override dialogClosed(): void {
    this._request += 1;
    this._parcelId = null;
    this._details = null;
    this._loading = false;
    this._loadError = null;
    this._mode = "view";
    this._pendingPrivate = null;
    this._checkRun += 1;
    this._checking = false;
    this._checkStatus = null;
    this._resetOrigins();
  }

  protected override canLightDismiss(): boolean {
    return this._mode === "view" && !this._busy;
  }

  protected override willUpdate(changed: PropertyValues): void {
    super.willUpdate(changed);
    if (!changed.has("snapshot") || !this.isOpen || !this.snapshot) {
      return;
    }
    this._pendingPrivate = null;
    const parcel = this.snapshot.parcels.find((item) => item.id === this._parcelId);
    // Reload the timeline when the parcel changed; a parcel that's gone shows "not found".
    if (parcel && JSON.stringify(parcel) !== this._loadedKey) {
      void this._load();
    }
  }

  private get _parcel(): Parcel | null {
    const id = this._parcelId;
    if (id === null) {
      return null;
    }
    if (this.snapshot) {
      return this.snapshot.parcels.find((parcel) => parcel.id === id) ?? null;
    }
    return this._details?.parcel ?? null;
  }

  private async _load(): Promise<void> {
    const hass = this.hass;
    const parcelId = this._parcelId;
    if (!hass || parcelId === null) {
      return;
    }
    const request = ++this._request;
    const current = this.snapshot?.parcels.find((parcel) => parcel.id === parcelId);
    this._loadedKey = current ? JSON.stringify(current) : "";
    this._loading = true;
    this._loadError = null;
    try {
      const raw = await callParcelsCommand<unknown>(hass, "get", { parcel_id: parcelId });
      if (request !== this._request) {
        return;
      }
      const details = normalizeDetails(raw);
      if (!details) {
        throw new Error(STRINGS.unknownError);
      }
      this._details = details;
    } catch (error) {
      if (request === this._request) {
        this._loadError = errorMessage(error);
      }
    } finally {
      if (request === this._request) {
        this._loading = false;
      }
    }
  }

  protected override renderContent(): TemplateResult {
    const parcel = this._parcel;
    return html`
      <div class="dialog-header">
        <div class="dialog-heading">
          <h2 id="dialog-title" class="dialog-title">
            ${parcel ? parcelTitle(parcel) : STRINGS.details}
          </h2>
          ${parcel ? this._renderBadges(parcel) : nothing}
        </div>
        <button
          type="button"
          class="icon-btn"
          data-autofocus
          aria-label=${STRINGS.close}
          title=${STRINGS.close}
          @click=${this.closeDialog}
        >
          <ha-icon icon="mdi:close" aria-hidden="true"></ha-icon>
        </button>
      </div>
      <div class="dialog-content">${this._renderBody(parcel)}</div>
      ${this._error
        ? html`<div class="dialog-error">
            <div class="alert error" role="alert">
              <ha-icon icon="mdi:alert-circle-outline" aria-hidden="true"></ha-icon>
              <span class="grow">${this._error}</span>
            </div>
          </div>`
        : nothing}
      ${this._mode === "view" ? this._renderStatus() : nothing}
      ${parcel && !parcel.restricted ? this._renderActions(parcel) : nothing}
    `;
  }

  /**
   * Always there in the view, so that screen readers announce what "Check
   * again" or a row of the "E-mails" section did, even when the parcel went.
   */
  private _renderStatus(): TemplateResult {
    const notice = this._originNotice;
    const busy = this._busy ? "true" : "false";
    return html`<div class="dialog-status" role="status">
      ${notice
        ? html`<div class="alert" data-origin-notice>
            <ha-icon icon="mdi:email-check-outline" aria-hidden="true"></ha-icon>
            <span class="grow">${notice.text}</span>
            ${notice.show
              ? html`<button
                  type="button"
                  class="btn"
                  aria-label=${STRINGS.showOtherParcelLabel}
                  aria-disabled=${busy}
                  @click=${() => this._showParcel(notice.show)}
                >
                  ${STRINGS.showOtherParcel}
                </button>`
              : nothing}
            ${notice.undo
              ? html`<button type="button" class="btn" aria-disabled=${busy} @click=${notice.undo}>
                  ${STRINGS.undo}
                </button>`
              : nothing}
            <button
              type="button"
              class="icon-btn"
              aria-label=${STRINGS.dismissMessage}
              title=${STRINGS.dismissMessage}
              @click=${this._dismissOriginNotice}
            >
              <ha-icon icon="mdi:close" aria-hidden="true"></ha-icon>
            </button>
          </div>`
        : nothing}
      ${this._checkStatus
        ? html`<div class="alert">
            <ha-icon icon="mdi:email-sync-outline" aria-hidden="true"></ha-icon>
            <span class="grow">${this._checkStatus}</span>
            <button
              type="button"
              class="icon-btn"
              aria-label=${STRINGS.dismissMessage}
              title=${STRINGS.dismissMessage}
              @click=${this._dismissCheckStatus}
            >
              <ha-icon icon="mdi:close" aria-hidden="true"></ha-icon>
            </button>
          </div>`
        : nothing}
    </div>`;
  }

  private _renderBadges(parcel: Parcel): TemplateResult {
    const aiLabel = parcel.ai ? STRINGS.aiBadgeLabel : STRINGS.aiFilledLabel;
    return html`<div class="dialog-badges">
      <span class="badge" style=${styleMap({ "--badge-color": statusColor(parcel.status) })}>
        ${statusLabel(parcel.status)}
      </span>
      ${(parcel.ai || parcel.ai_filled) && !parcel.restricted
        ? html`<span class="badge ai" title=${aiLabel}>
            ${STRINGS.aiBadge}<span class="sr-only">, ${aiLabel}</span>
          </span>`
        : nothing}
      ${parcel.private || parcel.restricted
        ? html`<span class="badge">
            <ha-icon icon="mdi:lock" aria-hidden="true"></ha-icon>${STRINGS.private}
          </span>`
        : nothing}
      ${parcel.provisional ? html`<span class="badge info">${STRINGS.provisional}</span>` : nothing}
      ${this._returnsOf(parcel).length
        ? html`<span class="badge return">
            <ha-icon icon=${RETURN_ICON} aria-hidden="true"></ha-icon>${STRINGS.returnBadge}
          </span>`
        : nothing}
      ${parcel.archived ? html`<span class="badge">${STRINGS.archived}</span>` : nothing}
    </div>`;
  }

  /** The customer returns of this parcel's items; none for someone else's private parcel. */
  private _returnsOf(parcel: Parcel): CustomerReturn[] {
    return parcel.restricted ? [] : returnsOfParcel(this.snapshot?.returns ?? [], parcel.id);
  }

  private _renderBody(parcel: Parcel | null): TemplateResult {
    if (!parcel) {
      if (this.snapshot || (!this._loading && !this._loadError)) {
        return html`<p class="empty">${STRINGS.notFound}</p>`;
      }
      return this._renderLoadState();
    }
    switch (this._mode) {
      case "date":
        return this._renderDateForm();
      case "merge":
        return this._renderMerge(parcel);
      case "split":
        return this._renderSplit();
      case "archive":
        return html`<p>${STRINGS.archiveQuestion}</p>`;
      default:
        return this._renderView(parcel);
    }
  }

  private _renderLoadState(): TemplateResult {
    if (this._loadError) {
      return html`<div class="alert error" role="alert">
        <ha-icon icon="mdi:alert-circle-outline" aria-hidden="true"></ha-icon>
        <span class="grow">${fmt(STRINGS.detailsError, { message: this._loadError })}</span>
        <button type="button" class="btn" @click=${this._load}>${STRINGS.retry}</button>
      </div>`;
    }
    return html`<p class="empty" role="status">${STRINGS.loadingDetails}</p>`;
  }

  private _renderView(parcel: Parcel): TemplateResult {
    const restricted = parcel.restricted;
    return html`
      ${!restricted && (parcel.ai || parcel.ai_filled)
        ? html`<div class="alert">
            <ha-icon icon="mdi:robot-outline" aria-hidden="true"></ha-icon>
            <span class="grow">${parcel.ai ? STRINGS.aiNotice : STRINGS.aiFilledNotice}</span>
            <button
              type="button"
              class="btn"
              aria-label=${parcel.ai ? STRINGS.confirmLabel : STRINGS.confirmFilledLabel}
              aria-disabled=${this._busy ? "true" : "false"}
              @click=${this._confirm}
            >
              ${STRINGS.confirm}
            </button>
          </div>`
        : nothing}
      ${!restricted && parcel.auto_merged ? this._renderMergeNotice(parcel) : nothing}
      ${!restricted && parcel.inferred ? this._renderInferredNotice(parcel) : nothing}
      ${!restricted && parcel.provisional
        ? html`<p class="hint">${STRINGS.provisionalHint}</p>`
        : nothing}
      ${restricted ? nothing : this._renderPossible(parcel)}
      ${this._renderFacts(parcel)}
      ${restricted
        ? nothing
        : html`<label class="check-row switch-row">
            <input
              type="checkbox"
              role="switch"
              .checked=${live(this._pendingPrivate ?? parcel.private)}
              aria-disabled=${this._busy ? "true" : "false"}
              @click=${this._onPrivateClick}
              @change=${this._togglePrivate}
            />
            <span>${STRINGS.fieldPrivate}</span>
          </label>`}
      ${restricted ? nothing : this._renderOrigins()}
      <h3 class="section-title">${STRINGS.timeline}</h3>
      ${this._details ? this._renderTimeline(this._details.timeline) : this._renderLoadState()}
    `;
  }

  /** The rows of the "E-mails" section; none until the details are loaded. */
  private get _rows(): OriginRow[] {
    const details = this._details;
    if (!details) {
      return [];
    }
    const cache = this._rowsCache;
    if (cache?.details === details && cache.locale === this.locale) {
      return cache.rows;
    }
    const rows = originRows(details.origins, this.locale);
    this._rowsCache = { details, locale: this.locale, rows };
    return rows;
  }

  /** The rows that can move to a new parcel: not the user's edits, which stay. */
  private get _splitRows(): OriginRow[] {
    return this._rows.filter((row) => !row.edits);
  }

  /** The chosen rows of a split that are still there. */
  private get _splitChosen(): string[] {
    const leads = new Set(this._splitRows.map((row) => row.lead));
    return this._splitSelection.filter((lead) => leads.has(lead));
  }

  /**
   * What each e-mail and source said and added, oldest first, closed until
   * opened. A row can move to a new parcel; an e-mail can leave Parcels
   * (administrators).
   */
  private _renderOrigins(): TemplateResult | typeof nothing {
    const rows = this._rows;
    if (!rows.length) {
      return nothing;
    }
    const movable = this._splitRows.length >= 2;
    return html`<details class="origins" .open=${this._originsOpen} @toggle=${this._onOriginsToggle}>
      <summary class="section-title" data-origins-summary>${originsTitle(rows)}</summary>
      <p class="hint">${STRINGS.originsHint}</p>
      <ol class="origin-list">
        ${originEntries(rows).map((entry) => this._renderOriginEntry(entry, movable))}
      </ol>
    </details>`;
  }

  private _renderOriginEntry(entry: OriginEntry, movable: boolean): TemplateResult {
    if (entry.type === "row") {
      return html`<li class="origin" data-origin=${entry.row.lead}>
        ${this._renderOriginBody(entry.row, false)}${this._renderRowActions(entry.row, movable)}
      </li>`;
    }
    const open = this._openFolds.has(entry.key);
    const latest = entry.latest.said;
    return html`<li class="origin fold">
      <span class="origin-line">
        <button
          type="button"
          class="link-btn fold-toggle"
          aria-expanded=${open ? "true" : "false"}
          @click=${() => this._toggleFold(entry.key)}
        >
          <ha-icon icon=${open ? "mdi:chevron-up" : "mdi:chevron-down"} aria-hidden="true"></ha-icon>
          ${fmt(STRINGS.originRepeats, { count: String(entry.rows.length), sender: entry.header })}
        </button>
        ${latest
          ? html`<span class="muted">· ${fmt(STRINGS.originRepeatsLatest, { said: latest })}</span>`
          : nothing}
      </span>
      ${open
        ? html`<ol class="origin-list">
            ${entry.rows.map(
              (row) => html`<li class="origin" data-origin=${row.lead}>
                ${this._renderOriginBody(row, false)}${this._renderRowActions(row, movable)}
              </li>`,
            )}
          </ol>`
        : nothing}
    </li>`;
  }

  /**
   * Who or what a row came from and when, what it said and what it added.
   * Inside a label (split) everything is a span.
   */
  private _renderOriginBody(row: OriginRow, inLabel: boolean): TemplateResult {
    let items: TemplateResult | typeof nothing = nothing;
    if (row.items.length && inLabel) {
      items = html`<span class="origin-line origin-items">
        ${row.items.map((item) => html`<span class="origin-item">${item}</span>`)}
      </span>`;
    } else if (row.items.length) {
      items = html`<ul class="origin-items" aria-label=${STRINGS.originItems}>
        ${row.items.map((item) => html`<li>${item}</li>`)}
      </ul>`;
    }
    const ai = row.ai === "all" ? STRINGS.originAiAll : STRINGS.originAiPart;
    return html`<span class="origin-line">
        <strong>${row.header}</strong>${row.when
          ? html`<span class="muted"> · ${row.when}</span>`
          : nothing}${row.ai ? html`<span class="muted"> · ${ai}</span>` : nothing}
      </span>
      ${row.said ? html`<span class="origin-line">${row.said}</span>` : nothing}
      ${row.facts.length
        ? html`<span class="origin-line muted">${row.facts.join(" · ")}</span>`
        : nothing}
      ${items}`;
  }

  /** Move to a new parcel (or why it can't), and Remove from Parcels for an administrator. */
  private _renderRowActions(row: OriginRow, movable: boolean): TemplateResult | typeof nothing {
    const remove = row.email && this.snapshot?.settings.user_is_admin === true;
    if (row.edits || (!movable && !remove)) {
      return nothing;
    }
    const blocked = movable ? splitBlockedReason(row.splitBlocked) : null;
    const busy = this._busy ? "true" : "false";
    const name = row.when ? `${row.header} · ${row.when}` : row.header;
    let move: TemplateResult | typeof nothing = nothing;
    if (blocked) {
      move = html`<span class="hint">${blocked}</span>`;
    } else if (movable) {
      move = html`<button
        type="button"
        class="btn"
        data-move
        aria-label=${fmt(STRINGS.moveToNewParcelLabel, { row: name })}
        aria-disabled=${busy}
        @click=${() => this._moveRow(row)}
      >
        ${STRINGS.moveToNewParcel}
      </button>`;
    }
    return html`<span class="row-actions">
      ${move}
      ${remove
        ? html`<button
            type="button"
            class="btn"
            data-remove
            aria-label=${fmt(STRINGS.removeFromParcelsLabel, { row: name })}
            aria-disabled=${busy}
            @click=${() => this._removeRow(row)}
          >
            ${STRINGS.removeFromParcels}
          </button>`
        : nothing}
    </span>`;
  }

  /**
   * The parcels a merge suggestion says this one may be (administrators only):
   * shown as uncertain, with Merge or "Not this one" for each.
   */
  private _renderPossible(parcel: Parcel): TemplateResult | typeof nothing {
    const suggestions = this.snapshot?.merge_suggestions;
    const matches = rankPossible(parcel, possibleMatches(suggestions, parcel.id), this._dayContext());
    if (!matches.length) {
      return nothing;
    }
    const locale = this.locale;
    const busy = this._busy ? "true" : "false";
    const title = parcelTitle(parcel);
    return html`<section class="possible" aria-labelledby="possible-title">
      <h3 class="section-title" id="possible-title">${STRINGS.possibleMatches}</h3>
      <p class="hint">${possibleHint(matches)}</p>
      <ul class="possible-list">
        ${matches.map((match) => {
          const candidate = candidateLabel(match.parcel, locale);
          return html`<li class="possible-item" data-possible=${match.parcel.id}>
            ${this._renderCandidateLines(match.parcel, parcel.id)}
            <span class="possible-actions">
              <button
                type="button"
                class="btn"
                data-accept
                aria-label=${fmt(STRINGS.mergeSuggestedLabel, { candidate, title })}
                aria-disabled=${busy}
                @click=${() => this._acceptPossible(match)}
              >
                ${STRINGS.mergeSuggested}
              </button>
              <button
                type="button"
                class="btn"
                data-dismiss
                aria-label=${fmt(STRINGS.notThisOneLabel, { candidate, title })}
                aria-disabled=${busy}
                @click=${() => this._dismissPossible(match)}
              >
                ${STRINGS.notThisOne}
              </button>
            </span>
          </li>`;
        })}
      </ul>
    </section>`;
  }

  private _renderMergeNotice(parcel: Parcel): TemplateResult {
    const reason = mergeReasonLabel(parcel.auto_merged?.reason);
    const busy = this._busy ? "true" : "false";
    const title = parcelTitle(parcel);
    return html`<div class="alert warning">
      <ha-icon icon="mdi:call-merge" aria-hidden="true"></ha-icon>
      <span class="grow">
        ${reason ? fmt(STRINGS.mergedNotice, { reason }) : STRINGS.mergedNoticeNoReason}
      </span>
      <button
        type="button"
        class="btn"
        aria-label=${fmt(STRINGS.undoMergeLabel, { title })}
        aria-disabled=${busy}
        @click=${this._undoMerge}
      >
        ${STRINGS.undo}
      </button>
      <button
        type="button"
        class="btn"
        aria-label=${fmt(STRINGS.keepMergeLabel, { title })}
        aria-disabled=${busy}
        @click=${this._keepMerge}
      >
        ${STRINGS.keep}
      </button>
    </div>`;
  }

  private _renderInferredNotice(parcel: Parcel): TemplateResult {
    const busy = this._busy ? "true" : "false";
    const title = parcelTitle(parcel);
    return html`<div class="alert warning">
      <ha-icon icon="mdi:package-variant-closed-check" aria-hidden="true"></ha-icon>
      <span class="grow">${inferredNotice(parcel)}</span>
      <button
        type="button"
        class="btn"
        aria-label=${fmt(STRINGS.undoInferredLabel, { title })}
        aria-disabled=${busy}
        @click=${this._undoInferred}
      >
        ${STRINGS.undo}
      </button>
      <button
        type="button"
        class="btn"
        aria-label=${fmt(STRINGS.keepInferredLabel, { title })}
        aria-disabled=${busy}
        @click=${this._keepInferred}
      >
        ${STRINGS.keep}
      </button>
    </div>`;
  }

  private _renderFacts(parcel: Parcel): TemplateResult {
    const locale = this.locale;
    const eta = etaRange(parcel);
    const window = formatWindow(parcel.window_start, parcel.window_end, locale);
    const carrier = carrierLabel(parcel);
    const url = parcel.restricted ? null : safeHttpsUrl(parcel.tracking_url);
    const number = parcel.tracking_number?.trim() ?? "";
    const orders = this._details?.orders ?? [];
    const packages = shipmentPackages(this.snapshot?.parcels ?? [], parcel);
    // The snapshot never holds the PIN; only the details of this parcel do.
    const loaded = this._details?.parcel.id === parcel.id ? this._details.parcel : null;
    const code = parcel.has_code ? (loaded?.pickup_code ?? null) : null;
    const returns = this._returnsOf(parcel);
    const row = (label: string, value: unknown): TemplateResult =>
      html`<div><dt>${label}</dt><dd>${value}</dd></div>`;
    const delivered = deliveredFact(parcel, locale);
    const nextAttempt = nextAttemptFact(parcel, this.snapshot?.settings.today ?? "", locale);
    const collectBy = collectByFact(parcel, locale);
    const etaSource = etaSourceLabel(parcel);
    const name = parcelAppName(parcel);
    return html`<dl class="facts">
      ${row(STRINGS.status, statusFact(parcel, locale))}
      ${delivered ? row(STRINGS.delivered, delivered) : nothing}
      ${nextAttempt ? row(STRINGS.nextAttempt, nextAttempt) : nothing}
      ${eta
        ? row(
            STRINGS.expected,
            `${formatDateRange(eta.start, eta.end, locale, EXPECTED_FORMAT)}${etaSource ? ` · ${etaSource}` : ""}`,
          )
        : nothing}
      ${window ? row(STRINGS.timeWindow, window) : nothing}
      ${returns.length
        ? row(
            STRINGS.returnBadge,
            html`<ul>
              ${returns.map((ret) => this._renderReturnLink(ret))}
            </ul>`,
          )
        : nothing}
      ${carrier || url || !parcel.restricted
        ? row(
            STRINGS.carrier,
            html`${carrier ?? (parcel.restricted ? "" : STRINGS.notKnownYet)}${url
              ? html`<a class="link" href=${url} target="_blank" rel="noopener noreferrer">
                  ${STRINGS.trackOnline}<span class="sr-only"> ${STRINGS.opensInNewTab}</span>
                  <ha-icon icon="mdi:open-in-new" aria-hidden="true"></ha-icon>
                </a>`
              : nothing}`,
          )
        : nothing}
      ${number
        ? html`<div>
            <dt><label for="tracking-number">${STRINGS.trackingNumber}</label></dt>
            <dd class="copy-row">
              <input id="tracking-number" readonly .value=${number} spellcheck="false" />
              <button
                type="button"
                class="btn"
                aria-label=${STRINGS.copyTrackingNumber}
                @click=${this._copy}
              >
                <ha-icon icon="mdi:content-copy" aria-hidden="true"></ha-icon>${STRINGS.copy}
              </button>
              <span class="copy-status hint" role="status">
                ${this._copyState === "copied"
                  ? STRINGS.copied
                  : this._copyState === "failed"
                    ? STRINGS.copyFailed
                    : ""}
              </span>
            </dd>
          </div>`
        : nothing}
      ${packages.length
        ? row(
            STRINGS.packagesInShipment,
            html`<ul class="packages">
              ${packages.map((item) => this._renderPackage(item, parcel.id))}
            </ul>`,
          )
        : nothing}
      ${parcel.merchant ? row(STRINGS.merchant, parcel.merchant) : nothing}
      ${parcel.seller ? row(STRINGS.seller, parcel.seller) : nothing}
      ${name ? row(STRINGS.parcelAppName, name) : nothing}
      ${orders.length
        ? row(
            STRINGS.orders,
            html`<ul>
              ${orders.map(
                (order) =>
                  html`<li>
                    ${order.number}${order.placed_at
                      ? ` · ${formatDateTime(order.placed_at, locale)}`
                      : ""}
                  </li>`,
              )}
            </ul>`,
          )
        : parcel.order_numbers.length
          ? row(STRINGS.orders, parcel.order_numbers.join(", "))
          : nothing}
      ${parcel.references.length ? row(STRINGS.references, parcel.references.join(", ")) : nothing}
      ${parcel.items.length
        ? row(
            STRINGS.items,
            html`<ul>
              ${parcel.items.map((item) => html`<li>${item}</li>`)}
            </ul>`,
          )
        : nothing}
      ${parcel.pickup_point ? row(STRINGS.pickupPoint, parcel.pickup_point) : nothing}
      ${collectBy ? row(STRINGS.collectBy, collectBy) : nothing}
      ${code ? row(STRINGS.pickupCode, code) : nothing}
      ${parcel.restricted ? nothing : row(STRINGS.parcelId, parcel.id)}
    </dl>`;
  }

  /** A return of this parcel's items: how far it is and its day; a tap shows the return. */
  private _renderReturnLink(ret: CustomerReturn): TemplateResult {
    const today = this.snapshot?.settings.today ?? "";
    const text = `${returnState(ret, today)} · ${formatDate(ret.day, this.locale)}`;
    if (ret.restricted) {
      return html`<li>${text}</li>`;
    }
    return html`<li>
      <button
        type="button"
        class="link-btn"
        aria-haspopup="dialog"
        aria-disabled=${this._busy ? "true" : "false"}
        @click=${() => this._openReturn(ret.id)}
      >
        ${text}
      </button>
    </li>`;
  }

  /** Closes this dialog, then asks the card to show the return. */
  private _openReturn(returnId: string): void {
    if (this._busy) {
      return;
    }
    this.closeDialog();
    this.dispatchEvent(new CustomEvent<string>(OPEN_RETURN_EVENT, { detail: returnId }));
  }

  /** A package of the shipment: its number, status and date; the others open on a tap. */
  private _renderPackage(item: Parcel, currentId: string): TemplateResult {
    const locale = this.locale;
    const name = item.tracking_number?.trim() || parcelTitle(item);
    const eta = etaRange(item);
    const when = item.delivered_undated
      ? (item.delivered_timeless && formatDayWithoutTime(item.delivered_at, locale, MEDIUM_DATE)) ||
        STRINGS.dateNotKnownInline
      : item.delivered_at
        ? formatDateTime(item.delivered_at, locale)
        : eta
        ? formatDateRange(eta.start, eta.end, locale)
        : "";
    const text = [statusLabel(item.status), when].filter(Boolean).join(" · ");
    if (item.id === currentId) {
      return html`<li aria-current="true" tabindex="-1" data-current-package>
        <strong>${name}</strong>${text ? ` · ${text}` : ""}
      </li>`;
    }
    return html`<li>
      <button
        type="button"
        class="link-btn"
        aria-label=${fmt(STRINGS.showPackage, { name })}
        aria-disabled=${this._busy ? "true" : "false"}
        @click=${() => this._switchTo(item.id)}
      >
        ${name}</button
      >${text ? ` · ${text}` : ""}
    </li>`;
  }

  private _renderTimeline(timeline: readonly TimelineEntry[]): TemplateResult {
    if (!timeline.length) {
      return html`<p class="muted">${STRINGS.noTimeline}</p>`;
    }
    const locale = this.locale;
    return html`<ol class="timeline">
      ${newestFirst(timeline).map((entry) => {
        const status = statusLabel(entry.status);
        const label = entry.label.trim();
        const time = entry.undated
          ? (entry.timeless && formatDayWithoutTime(entry.time, locale, MEDIUM_DATE)) || STRINGS.dateNotKnown
          : formatDateTime(entry.time, locale);
        const meta = [time, sourceLabel(entry.source)]
          .filter(Boolean)
          .join(" · ");
        return html`<li style=${styleMap({ "--dot-color": statusColor(entry.status) })}>
          <span class="dot" aria-hidden="true"></span>
          <div class="entry-title">${status}</div>
          ${label && label !== status ? html`<div>${label}</div>` : nothing}
          ${meta ? html`<div class="entry-meta">${meta}</div>` : nothing}
        </li>`;
      })}
    </ol>`;
  }

  private _renderDateForm(): TemplateResult {
    const form = this._dateForm;
    const error = this._formError;
    const field = (name: keyof DateForm, label: string, type: "date" | "time", first = false) => {
      const invalid = error?.field === name;
      return html`<label class="field">
        <span class="field-label">${label}</span>
        <input
          type=${type}
          name=${name}
          .value=${live(form[name])}
          ?data-first=${first}
          aria-invalid=${invalid ? "true" : "false"}
          aria-describedby=${invalid ? "date-error" : nothing}
          @input=${this._onDateInput}
        />
      </label>`;
    };
    return html`<form id="date-form" novalidate @submit=${this._saveDate}>
      <div class="form-grid">
        ${field("eta_start", STRINGS.fieldEtaStart, "date", true)}
        ${field("eta_end", STRINGS.fieldEtaEnd, "date")}
        ${field("window_start", STRINGS.fieldWindowStart, "time")}
        ${field("window_end", STRINGS.fieldWindowEnd, "time")}
      </div>
      ${error
        ? html`<div class="alert error" id="date-error" role="alert">
            <span class="grow">${error.message}</span>
          </div>`
        : nothing}
    </form>`;
  }

  private _renderMerge(parcel: Parcel): TemplateResult {
    const { pool, shown, target } = this._mergeChoice(parcel);
    const total = pool.likely.length + pool.older.length;
    if (!total) {
      return html`<p class="empty">${STRINGS.noMergeCandidates}</p>`;
    }
    const searching = this._mergeQuery.trim() !== "";
    const withSearch = total > SEARCH_FROM;
    const olderFirst = this._mergeOlder && !searching ? pool.likely.length : -1;
    const moreOlder = !searching && !this._mergeOlder && pool.older.length > 0;
    return html`<p id="merge-intro">${STRINGS.mergeIntro}</p>
      ${withSearch
        ? html`<label class="field">
            <span class="field-label">${STRINGS.mergeSearch}</span>
            <input
              type="search"
              data-first
              autocomplete="off"
              placeholder=${STRINGS.mergeSearchPlaceholder}
              .value=${live(this._mergeQuery)}
              @input=${this._onMergeQuery}
            />
          </label>`
        : nothing}
      <fieldset class="merge-list" aria-describedby="merge-intro">
        <legend class="sr-only">${STRINGS.mergeChoose}</legend>
        ${shown.map((candidate, index) =>
          this._renderCandidate(candidate, parcel.id, {
            checked: candidate.id === target,
            first: !withSearch && index === 0,
            olderFirst: index === olderFirst,
          }),
        )}
        ${searching && !shown.length ? html`<p class="empty">${STRINGS.mergeNoMatch}</p>` : nothing}
      </fieldset>
      ${moreOlder
        ? html`<button
            type="button"
            class="link-btn"
            ?data-first=${!withSearch && !shown.length}
            @click=${this._showOlderMerge}
          >
            ${fmt(STRINGS.mergeShowOlder, { count: String(pool.older.length) })}
          </button>`
        : nothing}
      ${this._mergeHint && !target
        ? html`<p class="hint merge-hint" role="alert">${STRINGS.mergeChooseFirst}</p>`
        : nothing}`;
  }

  private _renderCandidate(
    candidate: Parcel,
    parcelId: string,
    marks: { checked: boolean; first: boolean; olderFirst: boolean },
  ): TemplateResult {
    return html`<label class="merge-option">
      <input
        type="radio"
        name="merge-target"
        value=${candidate.id}
        .checked=${live(marks.checked)}
        ?data-first=${marks.first}
        ?data-older-first=${marks.olderFirst}
        @change=${this._onMergeTarget}
      />
      ${this._renderCandidateLines(candidate, parcelId)}
    </label>`;
  }

  /**
   * A parcel the viewed one may be: shop, status and day, carrier and
   * numbers, who wrote about it, and its items. Without items, why they
   * aren't known and which other orders it could also be.
   */
  private _renderCandidateLines(candidate: Parcel, parcelId: string): TemplateResult {
    const lines = candidateLines(candidate, this.locale);
    const also = lines.items
      ? null
      : couldAlsoBe(alsoPossible(this.snapshot?.merge_suggestions, candidate.id, parcelId));
    return html`<span class="merge-lines">
      <span class="merge-line"><strong>${lines.title}</strong> · ${lines.when}</span>
      <span class="merge-line muted">${lines.carrier}</span>
      ${lines.emails ? html`<span class="merge-line muted">${lines.emails}</span>` : nothing}
      <span class="merge-line items ${lines.items ? "" : "muted"}">
        ${lines.items ?? lines.noItems}
      </span>
      ${also ? html`<span class="merge-line items" data-also>${also}</span>` : nothing}
    </span>`;
  }

  /** Today and the server's time zone, from the snapshot. */
  private _dayContext(): DayContext {
    const settings = this.snapshot?.settings;
    return {
      today: settings?.today ?? "",
      timeZone: settings?.time_zone ?? Intl.DateTimeFormat().resolvedOptions().timeZone,
    };
  }

  private _renderSplit(): TemplateResult {
    return html`<fieldset aria-describedby="split-hint">
        <legend>${STRINGS.splitIntro}</legend>
        <div class="split-list">
          ${this._splitRows.map(
            (row, index) => html`<label class="check-row split-row">
              <input
                type="checkbox"
                .value=${row.lead}
                .checked=${live(this._splitSelection.includes(row.lead))}
                ?data-first=${index === 0}
                @change=${this._onSplitChange}
              />
              <span class="origin-body">${this._renderOriginBody(row, true)}</span>
            </label>`,
          )}
        </div>
      </fieldset>
      <p class="hint" id="split-hint">${STRINGS.splitHint}</p>`;
  }

  private _renderActions(parcel: Parcel): TemplateResult {
    const busy = this._busy ? "true" : "false";
    const cancel = html`<button type="button" class="btn" data-cancel @click=${this._backToView}>
      ${STRINGS.cancel}
    </button>`;
    switch (this._mode) {
      case "date":
        return html`<div class="dialog-actions">
          ${cancel}
          <button type="submit" form="date-form" class="btn primary" aria-disabled=${busy}>
            ${STRINGS.save}
          </button>
        </div>`;
      case "merge": {
        const { pool, target } = this._mergeChoice(parcel);
        return html`<div class="dialog-actions">
          ${cancel}
          ${pool.likely.length + pool.older.length
            ? html`<button
                type="button"
                class="btn primary"
                aria-disabled=${this._busy || !target ? "true" : "false"}
                @click=${this._merge}
              >
                ${STRINGS.mergeConfirm}
              </button>`
            : nothing}
        </div>`;
      }
      case "split": {
        const valid = isValidSplit(this._splitChosen, this._splitRows.length);
        return html`<div class="dialog-actions">
          ${cancel}
          <button
            type="button"
            class="btn primary"
            aria-disabled=${this._busy || !valid ? "true" : "false"}
            @click=${this._split}
          >
            ${STRINGS.splitConfirm}
          </button>
        </div>`;
      }
      case "archive":
        return html`<div class="dialog-actions">
          ${cancel}
          <button
            type="button"
            class="btn primary danger"
            aria-disabled=${busy}
            @click=${this._archive}
          >
            ${STRINGS.archive}
          </button>
        </div>`;
      default: {
        const canSplit = this._splitRows.length >= 2;
        return html`<div class="dialog-actions" role="group" aria-label=${STRINGS.actions}>
          <button type="button" class="btn" data-mode="date" @click=${this._editDate}>
            ${STRINGS.editDate}
          </button>
          ${canCheckAgain(parcel, this.snapshot?.settings.user_is_admin === true)
            ? html`<button
                type="button"
                class="btn"
                data-check-again
                title=${STRINGS.checkAgainHint}
                aria-disabled=${busy}
                @click=${this._checkAgain}
              >
                ${this._checking ? STRINGS.checkingAgain : STRINGS.checkAgain}
              </button>`
            : nothing}
          <button type="button" class="btn" data-mode="merge" @click=${this._startMerge}>
            ${STRINGS.mergeWith}
          </button>
          ${canSplit
            ? html`<button type="button" class="btn" data-mode="split" @click=${this._startSplit}>
                ${STRINGS.split}
              </button>`
            : nothing}
          ${parcel.archived
            ? nothing
            : html`<button
                type="button"
                class="btn danger"
                data-mode="archive"
                @click=${this._startArchive}
              >
                ${STRINGS.archive}
              </button>`}
          ${isActiveStatus(parcel.status)
            ? html`<span class="spacer"></span>
                <button
                  type="button"
                  class="btn primary"
                  aria-disabled=${busy}
                  @click=${this._markDelivered}
                >
                  <ha-icon icon="mdi:check" aria-hidden="true"></ha-icon>${STRINGS.markDelivered}
                </button>`
            : nothing}
        </div>`;
      }
    }
  }

  private _setMode(mode: Exclude<Mode, "view">): void {
    this._mode = mode;
    this._error = null;
    this._formError = null;
    void this.focusAfterRender(mode === "archive" ? "[data-cancel]" : "[data-first], [data-cancel]");
  }

  private _backToView(): void {
    const previous = this._mode;
    this._mode = "view";
    this._error = null;
    this._formError = null;
    void this.focusAfterRender(`[data-mode="${previous}"]`);
  }

  private _editDate(): void {
    const parcel = this._parcel;
    this._dateForm = parcel ? parcelToDateForm(parcel) : EMPTY_DATE_FORM;
    this._setMode("date");
  }

  private _startMerge(): void {
    this._mergeTarget = "";
    this._mergeQuery = "";
    this._mergeOlder = false;
    this._mergeHint = false;
    this._setMode("merge");
  }

  private _startSplit(): void {
    this._splitSelection = [];
    this._setMode("split");
  }

  private _startArchive(): void {
    this._setMode("archive");
  }

  /** The service call for the open parcel; `then` runs after success. */
  private _parcelService(
    service: string,
    data: Record<string, unknown>,
    then?: () => void,
  ): void {
    const hass = this.hass;
    const parcel = this._parcel;
    if (!hass || !parcel) {
      return;
    }
    void this.runAction(
      () => callParcelsService(hass, service, { parcel_id: parcel.id, ...data }),
      then,
    );
  }

  private _confirm(): void {
    this._parcelService("update", { confirm: true });
  }

  private _undoMerge(): void {
    this._parcelService("undo_merge", {});
  }

  private _keepMerge(): void {
    this._parcelService("update", { confirm_merge: true });
  }

  private _undoInferred(): void {
    this._parcelService("undo_delivery", {});
  }

  private _keepInferred(): void {
    this._parcelService("update", { confirm_delivery: true });
  }

  private _markDelivered(): void {
    this._parcelService("mark_delivered", {});
  }

  /** Reads the parcel's e-mails again; the parcel stays, and the answer says what happened. */
  private async _checkAgain(): Promise<void> {
    const hass = this.hass;
    const parcel = this._parcel;
    if (!hass || !parcel || this._busy) {
      return;
    }
    const run = ++this._checkRun;
    let result = normalizeCheckAgain(null);
    this._checkStatus = null;
    this._checking = true;
    await this.runAction(
      async () => {
        const raw = await callParcelsCommand<unknown>(hass, "parcel/check_again", {
          parcel_id: parcel.id,
        });
        result = normalizeCheckAgain(raw);
      },
      () => {
        const settings = this.snapshot?.settings;
        this._checkStatus = checkAgainText(result, {
          enabled: settings?.ai_enabled === true,
          mode: settings?.ai_mode ?? "off",
        });
      },
    );
    if (run === this._checkRun) {
      this._checking = false;
    }
  }

  private _dismissCheckStatus(): void {
    this._checkStatus = null;
  }

  private _archive(): void {
    this._parcelService("archive", {}, () => this.closeDialog());
  }

  private _onPrivateClick(event: MouseEvent): void {
    // A disabled-looking switch must not change while a call runs.
    if (this._busy) {
      event.preventDefault();
    }
  }

  private _togglePrivate(event: Event): void {
    const value = (event.currentTarget as HTMLInputElement).checked;
    const hass = this.hass;
    const parcel = this._parcel;
    if (!hass || !parcel || this._busy) {
      return;
    }
    this._pendingPrivate = value;
    void this.runAction(async () => {
      try {
        await callParcelsService(hass, "update", { parcel_id: parcel.id, private: value });
      } catch (error) {
        this._pendingPrivate = null;
        throw error;
      }
    });
  }

  private _onDateInput(event: Event): void {
    const input = event.currentTarget as HTMLInputElement;
    const name = input.name as keyof DateForm;
    this._dateForm = { ...this._dateForm, [name]: input.value };
    this._formError = null;
  }

  private _saveDate(event: Event): void {
    event.preventDefault();
    const parcel = this._parcel;
    if (!parcel || this._busy) {
      return;
    }
    const form = this._dateForm;
    const problem = dateProblem(form);
    if (problem) {
      this._formError = problem;
      void this.focusAfterRender(`[name="${problem.field}"]`);
      return;
    }
    const data = dateFormToUpdate(parcel.id, form);
    this._parcelService("update", data, () => this._backToView());
  }

  /** Every other parcel the viewer may see, likely matches first. */
  private _mergePool(parcel: Parcel): MergeCandidates {
    const snapshot = this.snapshot;
    if (!snapshot) {
      return { likely: [], older: [] };
    }
    return rankMergeCandidates(snapshot.parcels, parcel, this._dayContext());
  }

  /** The candidates on show, and the chosen one while it is on show. */
  private _mergeChoice(parcel: Parcel): { pool: MergeCandidates; shown: Parcel[]; target: string } {
    const pool = this._mergePool(parcel);
    const query = this._mergeQuery.trim();
    let shown = pool.likely;
    if (query) {
      shown = searchCandidates([...pool.likely, ...pool.older], query);
    } else if (this._mergeOlder) {
      shown = [...pool.likely, ...pool.older];
    }
    const target = shown.some((candidate) => candidate.id === this._mergeTarget) ? this._mergeTarget : "";
    return { pool, shown, target };
  }

  private _onMergeTarget(event: Event): void {
    this._mergeTarget = (event.currentTarget as HTMLInputElement).value;
    this._mergeHint = false;
  }

  private _onMergeQuery(event: Event): void {
    this._mergeQuery = (event.currentTarget as HTMLInputElement).value;
  }

  private _showOlderMerge(): void {
    this._mergeOlder = true;
    void this.focusAfterRender("[data-older-first]");
  }

  /** Merges a possible match; the dialog follows the parcel that remains. */
  private _acceptPossible(match: PossibleMatch): void {
    const hass = this.hass;
    if (!hass) {
      return;
    }
    let merged: string | null = null;
    void this.runAction(
      async () => {
        const result = await callParcelsCommand<{ parcel_id?: unknown }>(
          hass,
          "suggestion/accept",
          { suggestion_id: match.suggestionId, parcel_id: match.candidateId },
        );
        merged = typeof result?.parcel_id === "string" ? result.parcel_id : null;
      },
      () => {
        if (merged !== null && merged !== this._parcelId) {
          this._parcelId = merged;
          this._details = null;
          this._loadError = null;
          void this._load();
        }
        void this.focusAfterRender("[data-autofocus]");
      },
    );
  }

  /** Rules a possible match out: the two parcels are kept apart. */
  private _dismissPossible(match: PossibleMatch): void {
    const hass = this.hass;
    if (!hass) {
      return;
    }
    void this.runAction(
      () =>
        callParcelsCommand(hass, "suggestion/dismiss", {
          suggestion_id: match.suggestionId,
          parcel_id: match.candidateId,
        }),
      () => void this.focusAfterRender("[data-autofocus]"),
    );
  }

  private _merge(): void {
    const hass = this.hass;
    const parcel = this._parcel;
    if (!hass || !parcel) {
      return;
    }
    const { target } = this._mergeChoice(parcel);
    if (!target) {
      this._mergeHint = true;
      void this.focusAfterRender('input[name="merge-target"]');
      return;
    }
    // The open parcel is the target: the chosen one is merged into it.
    void this.runAction(
      () => callParcelsService(hass, "merge", { parcel_ids: [parcel.id, target] }),
      () => this._backToView(),
    );
  }

  private _onSplitChange(event: Event): void {
    const input = event.currentTarget as HTMLInputElement;
    const others = this._splitSelection.filter((id) => id !== input.value);
    this._splitSelection = input.checked ? [...others, input.value] : others;
  }

  private _split(): void {
    const rows = this._splitRows;
    const chosen = this._splitChosen;
    if (!isValidSplit(chosen, rows.length)) {
      return;
    }
    // A row moves with what the local AI read in its e-mail.
    this._parcelService("split", { origins: rowIds(rows, chosen) }, () => this._backToView());
  }

  private _onOriginsToggle(event: Event): void {
    this._originsOpen = (event.currentTarget as HTMLDetailsElement).open;
  }

  private _toggleFold(key: string): void {
    const folds = new Set(this._openFolds);
    if (!folds.delete(key)) {
      folds.add(key);
    }
    this._openFolds = folds;
  }

  private _dismissOriginNotice(): void {
    this._originNotice = null;
  }

  private _showParcel(parcelId: string | null): void {
    if (parcelId !== null) {
      this._switchTo(parcelId);
    }
  }

  /** After a row action, focus stays with the "E-mails" section, or goes to the close button. */
  private async _focusOrigins(): Promise<void> {
    await this.updateComplete;
    if (!this.isOpen) {
      return;
    }
    const summary = this.renderRoot.querySelector<HTMLElement>("dialog [data-origins-summary]");
    if (summary) {
      summary.focus();
    } else {
      this.focusInDialog("[data-autofocus]");
    }
  }

  /** Moves a row, with what the local AI read in its e-mail, to a new parcel; Undo merges it back. */
  private _moveRow(row: OriginRow): void {
    const hass = this.hass;
    const parcel = this._parcel;
    if (!hass || !parcel || this._busy) {
      return;
    }
    const parcelId = parcel.id;
    let created: string | null = null;
    this._originNotice = null;
    void this.runAction(
      async () => {
        created = await callParcelsServiceForParcel(hass, "split", {
          parcel_id: parcelId,
          origins: row.ids,
        });
      },
      () => {
        const moved = created;
        this._originNotice = {
          text: STRINGS.movedNotice,
          undo: moved === null ? null : () => this._moveBack(parcelId, moved),
          show: moved,
        };
        void this._load();
        void this._focusOrigins();
      },
    );
  }

  private _moveBack(parcelId: string, moved: string): void {
    const hass = this.hass;
    if (!hass || this._busy) {
      return;
    }
    void this.runAction(
      () => callParcelsService(hass, "merge", { parcel_ids: [parcelId, moved] }),
      () => {
        this._originNotice = { text: STRINGS.movedBackNotice, undo: null, show: null };
        void this._load();
        void this._focusOrigins();
      },
    );
  }

  /**
   * Removes an e-mail from Parcels, with what it added (administrators). It
   * waits under Filtered; Undo restores it, and it's read again.
   */
  private _removeRow(row: OriginRow): void {
    const hass = this.hass;
    const parcel = this._parcel;
    if (!hass || !parcel || this._busy) {
      return;
    }
    const parcelId = parcel.id;
    let filtered: string | null = null;
    let kept = true;
    this._originNotice = null;
    void this.runAction(
      async () => {
        const result = await callParcelsCommand<{ filtered_id?: unknown; parcel_id?: unknown }>(
          hass,
          "origin/remove",
          { parcel_id: parcelId, origin_id: row.lead },
        );
        filtered = typeof result?.filtered_id === "string" ? result.filtered_id : null;
        kept = typeof result?.parcel_id === "string";
      },
      () => {
        const entry = filtered;
        this._originNotice = {
          text: kept ? STRINGS.removedNotice : STRINGS.removedGoneNotice,
          undo: entry === null ? null : () => this._restoreRow(entry, parcelId),
          show: null,
        };
        if (kept) {
          void this._load();
        }
        void this._focusOrigins();
      },
    );
  }

  /** Restores a removed e-mail; the dialog follows it when its parcel went with it. */
  private _restoreRow(filteredId: string, parcelId: string): void {
    const hass = this.hass;
    if (!hass || this._busy) {
      return;
    }
    let review: string | null = null;
    let parcels: string[] = [];
    void this.runAction(
      async () => {
        const result = await callParcelsCommand<{ review_id?: unknown; parcel_ids?: unknown }>(
          hass,
          "review/restore",
          { filtered_id: filteredId },
        );
        review = typeof result?.review_id === "string" ? result.review_id : null;
        const ids = result?.parcel_ids;
        parcels = Array.isArray(ids) ? ids.filter((id): id is string => typeof id === "string") : [];
      },
      () => {
        const gone =
          this._parcelId === parcelId &&
          !this.snapshot?.parcels.some((item) => item.id === parcelId);
        const outcome = restoreOutcome({ review, parcels }, parcelId, gone);
        if (outcome.follow !== null) {
          this._parcelId = outcome.follow;
          this._details = null;
          this._loadError = null;
        }
        this._originNotice = {
          text: RESTORE_NOTICES[outcome.notice],
          undo: null,
          show: outcome.show,
        };
        void this._load();
        void this._focusOrigins();
      },
    );
  }

  private async _copy(event: MouseEvent): Promise<void> {
    const button = event.currentTarget as HTMLElement;
    const number = this._parcel?.tracking_number?.trim();
    if (!number) {
      return;
    }
    this._copyState = "idle";
    try {
      if (!navigator.clipboard?.writeText) {
        throw new Error("Clipboard API unavailable");
      }
      await navigator.clipboard.writeText(number);
      this._copyState = "copied";
      return;
    } catch {
      // Not available (e.g. Home Assistant over plain http): copy the selected text instead.
    }
    const input = this.renderRoot.querySelector<HTMLInputElement>("#tracking-number");
    input?.focus();
    input?.select();
    let copied = false;
    try {
      copied = document.execCommand("copy");
    } catch {
      copied = false;
    }
    this._copyState = copied ? "copied" : "failed";
    if (copied) {
      button.focus();
    }
  }
}

defineElement("parcels-details-dialog", ParcelsDetailsDialog);

declare global {
  interface HTMLElementTagNameMap {
    "parcels-details-dialog": ParcelsDetailsDialog;
  }
}
