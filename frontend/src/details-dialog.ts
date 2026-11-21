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
import { callParcelsCommand, callParcelsService } from "./api.ts";
import { canCheckAgain, checkAgainText, normalizeCheckAgain } from "./check-again.ts";
import { parseInstant } from "./dates.ts";
import { candidateLabel, candidateLines } from "./describe.ts";
import { ParcelsDialogBase, OPEN_RETURN_EVENT, type ReturnFocus } from "./dialog-base.ts";
import { errorMessage } from "./errors.ts";
import {
  formatDate,
  formatDateRange,
  formatDateTime,
  formatWindow,
  localeOptions,
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
  etaRange,
  possibleMatches,
  rankMergeCandidates,
  searchCandidates,
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

const EXPECTED_FORMAT: Intl.DateTimeFormatOptions = {
  weekday: "short",
  day: "numeric",
  month: "short",
  year: "numeric",
};

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

  /** Counts loads, so that only the latest result is shown. */
  private _request = 0;
  /** Counts "Check again" runs, so that a late one doesn't end a newer one. */
  private _checkRun = 0;
  /** The snapshot parcel the details were loaded for. */
  private _loadedKey = "";

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
    void this._load();
    void this.focusAfterRender("[data-current-package]");
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
      ${parcel && this._mode === "view" ? this._renderCheckStatus() : nothing}
      ${parcel && !parcel.restricted ? this._renderActions(parcel) : nothing}
    `;
  }

  /** Always there in the view, so that screen readers announce what "Check again" did. */
  private _renderCheckStatus(): TemplateResult {
    return html`<div class="dialog-status" role="status">
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
      <h3 class="section-title">${STRINGS.timeline}</h3>
      ${this._details ? this._renderTimeline(this._details.timeline) : this._renderLoadState()}
    `;
  }

  /**
   * The parcels a merge suggestion says this one may be (administrators only):
   * shown as uncertain, with Merge or "Not this one" for each.
   */
  private _renderPossible(parcel: Parcel): TemplateResult | typeof nothing {
    const matches = possibleMatches(this.snapshot?.merge_suggestions, parcel.id);
    if (!matches.length) {
      return nothing;
    }
    const locale = this.locale;
    const busy = this._busy ? "true" : "false";
    const title = parcelTitle(parcel);
    return html`<section class="possible" aria-labelledby="possible-title">
      <h3 class="section-title" id="possible-title">${STRINGS.possibleMatches}</h3>
      <p class="hint">${STRINGS.possibleMatchesHint}</p>
      <ul class="possible-list">
        ${matches.map((match) => {
          const lines = candidateLines(match.parcel, locale);
          const candidate = candidateLabel(match.parcel, locale);
          return html`<li class="possible-item" data-possible=${match.parcel.id}>
            <span class="merge-lines">
              <span class="merge-line"><strong>${lines.title}</strong> · ${lines.when}</span>
              <span class="merge-line muted">${lines.carrier}</span>
              <span class="merge-line items ${lines.items ? "" : "muted"}">
                ${lines.items ?? STRINGS.itemsNotKnown}
              </span>
            </span>
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
    const since = parcel.status_undated
      ? ` · ${STRINGS.dateNotKnownInline}`
      : parcel.status_time
        ? ` · ${fmt(STRINGS.sinceDate, { date: formatDateTime(parcel.status_time, locale) })}`
        : "";
    const etaSource = etaSourceLabel(parcel);
    const name = parcelAppName(parcel);
    return html`<dl class="facts">
      ${row(STRINGS.status, `${statusLabel(parcel.status)}${since}`)}
      ${parcel.delivered_undated
        ? row(STRINGS.delivered, STRINGS.dateNotKnown)
        : parcel.delivered_at
          ? row(STRINGS.delivered, formatDateTime(parcel.delivered_at, locale))
          : nothing}
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
      ? STRINGS.dateNotKnownInline
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
        const time = entry.undated ? STRINGS.dateNotKnown : formatDateTime(entry.time, locale);
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
          this._renderCandidate(candidate, {
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
    marks: { checked: boolean; first: boolean; olderFirst: boolean },
  ): TemplateResult {
    const lines = candidateLines(candidate, this.locale);
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
      <span class="merge-lines">
        <span class="merge-line"><strong>${lines.title}</strong> · ${lines.when}</span>
        <span class="merge-line muted">${lines.carrier}</span>
        <span class="merge-line items ${lines.items ? "" : "muted"}">
          ${lines.items ?? STRINGS.itemsNotKnown}
        </span>
      </span>
    </label>`;
  }

  private _renderSplit(): TemplateResult {
    const origins = this._details?.origins ?? [];
    const locale = this.locale;
    return html`<fieldset aria-describedby="split-hint">
        <legend>${STRINGS.splitIntro}</legend>
        ${origins.map((origin, index) => {
          const time = origin.time ? formatDateTime(origin.time, locale) : "";
          return html`<label class="check-row">
            <input
              type="checkbox"
              .value=${origin.id}
              .checked=${live(this._splitSelection.includes(origin.id))}
              ?data-first=${index === 0}
              @change=${this._onSplitChange}
            />
            <span>
              ${origin.label.trim() || sourceLabel(origin.source)}${time
                ? html`<span class="muted"> · ${time}</span>`
                : nothing}
            </span>
          </label>`;
        })}
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
        const valid = isValidSplit(this._splitSelection, this._details?.origins.length ?? 0);
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
        const canSplit = (this._details?.origins.length ?? 0) >= 2;
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
    return rankMergeCandidates(snapshot.parcels, parcel, {
      today: snapshot.settings.today,
      timeZone: snapshot.settings.time_zone,
    });
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
    const total = this._details?.origins.length ?? 0;
    if (!isValidSplit(this._splitSelection, total)) {
      return;
    }
    this._parcelService("split", { origins: [...this._splitSelection] }, () => this._backToView());
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
