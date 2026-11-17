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
import { parseInstant } from "./dates.ts";
import { candidateLabel } from "./describe.ts";
import { ParcelsDialogBase, type ReturnFocus } from "./dialog-base.ts";
import { errorMessage } from "./errors.ts";
import {
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
import {
  carrierLabel,
  mergeReasonLabel,
  parcelTitle,
  sourceLabel,
  statusLabel,
} from "./labels.ts";
import { normalizeDetails } from "./normalize.ts";
import { etaRange, mergeCandidates } from "./parcels.ts";
import { defineElement } from "./register.ts";
import { isActiveStatus, statusColor } from "./status.ts";
import { STRINGS, fmt } from "./strings.ts";
import { baseStyles, dialogStyles } from "./styles.ts";
import { safeHttpsUrl } from "./url.ts";
import type { Parcel, ParcelDetails, Snapshot, TimelineEntry } from "./types.ts";

type Mode = "view" | "date" | "merge" | "split" | "archive";
type CopyState = "idle" | "copied" | "failed";

const EXPECTED_FORMAT: Intl.DateTimeFormatOptions = {
  weekday: "short",
  day: "numeric",
  month: "short",
  year: "numeric",
};

const EMPTY_DATE_FORM: DateForm = { eta_start: "", eta_end: "", window_start: "", window_end: "" };

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
    _splitSelection: { state: true },
    _pendingPrivate: { state: true },
  };

  static override styles: CSSResultGroup = [
    baseStyles,
    dialogStyles,
    css`
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
  declare private _splitSelection: readonly string[];
  /** The private value just chosen, until the next snapshot. */
  declare private _pendingPrivate: boolean | null;

  /** Counts loads, so that only the latest result is shown. */
  private _request = 0;
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
    this._splitSelection = [];
    this._pendingPrivate = null;
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
    void this._load();
    await this.showDialog(returnFocus);
  }

  protected override dialogClosed(): void {
    this._request += 1;
    this._parcelId = null;
    this._details = null;
    this._loading = false;
    this._loadError = null;
    this._mode = "view";
    this._pendingPrivate = null;
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
      ${parcel && !parcel.restricted ? this._renderActions(parcel) : nothing}
    `;
  }

  private _renderBadges(parcel: Parcel): TemplateResult {
    return html`<div class="dialog-badges">
      <span class="badge" style=${styleMap({ "--badge-color": statusColor(parcel.status) })}>
        ${statusLabel(parcel.status)}
      </span>
      ${parcel.ai && !parcel.restricted
        ? html`<span class="badge ai" title=${STRINGS.aiBadgeLabel}>
            ${STRINGS.aiBadge}<span class="sr-only">, ${STRINGS.aiBadgeLabel}</span>
          </span>`
        : nothing}
      ${parcel.private || parcel.restricted
        ? html`<span class="badge">
            <ha-icon icon="mdi:lock" aria-hidden="true"></ha-icon>${STRINGS.private}
          </span>`
        : nothing}
      ${parcel.provisional ? html`<span class="badge info">${STRINGS.provisional}</span>` : nothing}
      ${parcel.archived ? html`<span class="badge">${STRINGS.archived}</span>` : nothing}
    </div>`;
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
      ${!restricted && parcel.ai
        ? html`<div class="alert">
            <ha-icon icon="mdi:robot-outline" aria-hidden="true"></ha-icon>
            <span class="grow">${STRINGS.aiNotice}</span>
            <button
              type="button"
              class="btn"
              aria-label=${STRINGS.confirmLabel}
              aria-disabled=${this._busy ? "true" : "false"}
              @click=${this._confirm}
            >
              ${STRINGS.confirm}
            </button>
          </div>`
        : nothing}
      ${!restricted && parcel.auto_merged ? this._renderMergeNotice(parcel) : nothing}
      ${!restricted && parcel.provisional
        ? html`<p class="hint">${STRINGS.provisionalHint}</p>`
        : nothing}
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

  private _renderFacts(parcel: Parcel): TemplateResult {
    const locale = this.locale;
    const eta = etaRange(parcel);
    const window = formatWindow(parcel.window_start, parcel.window_end, locale);
    const carrier = carrierLabel(parcel);
    const url = parcel.restricted ? null : safeHttpsUrl(parcel.tracking_url);
    const number = parcel.tracking_number?.trim() ?? "";
    const orders = this._details?.orders ?? [];
    const row = (label: string, value: unknown): TemplateResult =>
      html`<div><dt>${label}</dt><dd>${value}</dd></div>`;
    const since = parcel.status_time
      ? ` · ${fmt(STRINGS.sinceDate, { date: formatDateTime(parcel.status_time, locale) })}`
      : "";
    return html`<dl class="facts">
      ${row(STRINGS.status, `${statusLabel(parcel.status)}${since}`)}
      ${parcel.delivered_at
        ? row(STRINGS.delivered, formatDateTime(parcel.delivered_at, locale))
        : nothing}
      ${eta
        ? row(STRINGS.expected, formatDateRange(eta.start, eta.end, locale, EXPECTED_FORMAT))
        : nothing}
      ${window ? row(STRINGS.timeWindow, window) : nothing}
      ${carrier || url
        ? row(
            STRINGS.carrier,
            html`${carrier ?? ""}${url
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
      ${parcel.merchant ? row(STRINGS.merchant, parcel.merchant) : nothing}
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
      ${parcel.items.length
        ? row(
            STRINGS.items,
            html`<ul>
              ${parcel.items.map((item) => html`<li>${item}</li>`)}
            </ul>`,
          )
        : nothing}
      ${parcel.pickup_point ? row(STRINGS.pickupPoint, parcel.pickup_point) : nothing}
      ${parcel.pickup_code ? row(STRINGS.pickupCode, parcel.pickup_code) : nothing}
    </dl>`;
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
        const meta = [formatDateTime(entry.time, locale), sourceLabel(entry.source)]
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
    const candidates = mergeCandidates(this.snapshot?.parcels ?? [], parcel.id);
    if (!candidates.length) {
      return html`<p class="empty">${STRINGS.noMergeCandidates}</p>`;
    }
    const target = this._resolvedMergeTarget(candidates);
    return html`<p>${STRINGS.mergeIntro}</p>
      <label class="field">
        <span class="field-label">${STRINGS.mergeChoose}</span>
        <select data-first @change=${this._onMergeTarget}>
          ${candidates.map(
            (candidate) =>
              html`<option value=${candidate.id} ?selected=${candidate.id === target}>
                ${candidateLabel(candidate, this.locale)}
              </option>`,
          )}
        </select>
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
        const candidates = mergeCandidates(this.snapshot?.parcels ?? [], parcel.id);
        return html`<div class="dialog-actions">
          ${cancel}
          ${candidates.length
            ? html`<button
                type="button"
                class="btn primary"
                aria-disabled=${busy}
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

  private _markDelivered(): void {
    this._parcelService("mark_delivered", {});
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

  private _resolvedMergeTarget(candidates: readonly Parcel[]): string {
    return candidates.some((candidate) => candidate.id === this._mergeTarget)
      ? this._mergeTarget
      : (candidates[0]?.id ?? "");
  }

  private _onMergeTarget(event: Event): void {
    this._mergeTarget = (event.currentTarget as HTMLSelectElement).value;
  }

  private _merge(): void {
    const hass = this.hass;
    const parcel = this._parcel;
    if (!hass || !parcel) {
      return;
    }
    const target = this._resolvedMergeTarget(
      mergeCandidates(this.snapshot?.parcels ?? [], parcel.id),
    );
    if (!target) {
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
