/** The details of a customer return: its pickup, carrier, items and e-mails. */
import {
  css,
  html,
  nothing,
  type CSSResultGroup,
  type PropertyDeclarations,
  type TemplateResult,
} from "lit";
import { callParcelsCommand } from "./api.ts";
import { OPEN_PARCEL_EVENT, ParcelsDialogBase, type ReturnFocus } from "./dialog-base.ts";
import { formatDate, formatDateTime, localeOptions, type LocaleOptions } from "./format.ts";
import { carrierLabel, parcelTitle, sourceLabel, statusLabel } from "./labels.ts";
import { defineElement } from "./register.ts";
import { RETURN_ICON, pickupRuleText, returnState, returnTitle } from "./returns.ts";
import { STRINGS, fmt } from "./strings.ts";
import { baseStyles, dialogStyles } from "./styles.ts";
import { safeHttpsUrl } from "./url.ts";
import type { CustomerReturn, Parcel, Snapshot } from "./types.ts";

type Mode = "view" | "remove";

export class ParcelsReturnDialog extends ParcelsDialogBase {
  static override properties: PropertyDeclarations = {
    snapshot: { attribute: false },
    locale: { attribute: false },
    _returnId: { state: true },
    _mode: { state: true },
  };

  static override styles: CSSResultGroup = [
    baseStyles,
    dialogStyles,
    css`
      .facts {
        display: flex;
        flex-direction: column;
        gap: 8px;
        margin: 12px 0 0;
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
      .facts .hint {
        margin-top: 2px;
      }
      .link {
        display: inline-flex;
        align-items: center;
        gap: 4px;
        margin-inline-start: 8px;
        --mdc-icon-size: 16px;
      }
      .emails .entry-meta {
        font-size: 0.8125rem;
        color: var(--secondary-text-color, #727272);
      }
    `,
  ];

  /** The latest snapshot, from the card. */
  declare snapshot: Snapshot | null;
  declare locale: LocaleOptions;
  declare private _returnId: string | null;
  declare private _mode: Mode;

  constructor() {
    super();
    this.snapshot = null;
    this.locale = localeOptions(undefined);
    this._returnId = null;
    this._mode = "view";
  }

  /** Opens the dialog for a return; `returnFocus` runs when it closes. */
  async open(returnId: string, returnFocus: ReturnFocus | null = null): Promise<void> {
    this._returnId = returnId;
    this._mode = "view";
    await this.showDialog(returnFocus);
  }

  protected override dialogClosed(): void {
    this._returnId = null;
    this._mode = "view";
  }

  protected override canLightDismiss(): boolean {
    return this._mode === "view" && !this._busy;
  }

  private get _return(): CustomerReturn | null {
    const id = this._returnId;
    return id === null ? null : (this.snapshot?.returns.find((ret) => ret.id === id) ?? null);
  }

  protected override renderContent(): TemplateResult {
    const ret = this._return;
    const today = this.snapshot?.settings.today ?? "";
    return html`
      <div class="dialog-header">
        <div class="dialog-heading">
          <h2 id="dialog-title" class="dialog-title">
            ${ret ? returnTitle(ret) : STRINGS.returnDetails}
          </h2>
          ${ret ? this._renderBadges(ret, today) : nothing}
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
      <div class="dialog-content">${this._renderBody(ret)}</div>
      ${this._error
        ? html`<div class="dialog-error">
            <div class="alert error" role="alert">
              <ha-icon icon="mdi:alert-circle-outline" aria-hidden="true"></ha-icon>
              <span class="grow">${this._error}</span>
            </div>
          </div>`
        : nothing}
      ${ret && !ret.restricted && this.snapshot?.settings.user_is_admin === true
        ? this._renderActions()
        : nothing}
    `;
  }

  /** How far it is, in the returns colour with its icon, so it doesn't need the colour. */
  private _renderBadges(ret: CustomerReturn, today: string): TemplateResult {
    return html`<div class="dialog-badges">
      <span class="badge return">
        <ha-icon icon=${RETURN_ICON} aria-hidden="true"></ha-icon>${returnState(ret, today)}
      </span>
      ${ret.private || ret.restricted
        ? html`<span class="badge">
            <ha-icon icon="mdi:lock" aria-hidden="true"></ha-icon>${STRINGS.private}
          </span>`
        : nothing}
      ${ret.archived ? html`<span class="badge">${STRINGS.archived}</span>` : nothing}
    </div>`;
  }

  private _renderBody(ret: CustomerReturn | null): TemplateResult {
    if (!ret) {
      return html`<p class="empty">${STRINGS.returnNotFound}</p>`;
    }
    if (this._mode === "remove") {
      return html`<p>${STRINGS.removeReturnQuestion}</p>`;
    }
    return html`<p class="hint">${STRINGS.returnHint}</p>
      ${this._renderFacts(ret)}`;
  }

  private _renderFacts(ret: CustomerReturn): TemplateResult {
    const locale = this.locale;
    const row = (label: string, value: unknown): TemplateResult =>
      html`<div><dt>${label}</dt><dd>${value}</dd></div>`;
    const rule = pickupRuleText(ret.pickup_rule);
    const carrier = ret.restricted ? null : carrierLabel(ret);
    const url = ret.restricted ? null : safeHttpsUrl(ret.tracking_url);
    const number = ret.tracking_number?.trim() ?? "";
    const parcels = this._parcels(ret);
    return html`<dl class="facts">
      ${ret.pickup
        ? row(
            STRINGS.pickup,
            html`${formatDate(ret.pickup, locale)}${rule
              ? html`<div class="hint">${rule}</div>`
              : nothing}`,
          )
        : nothing}
      ${ret.started ? row(STRINGS.returnStartedDay, formatDateTime(ret.started, locale)) : nothing}
      ${carrier || url
        ? row(
            STRINGS.returnCarrier,
            html`${carrier ?? ""}${url
              ? html`<a class="link" href=${url} target="_blank" rel="noopener noreferrer">
                  ${STRINGS.trackOnline}<span class="sr-only"> ${STRINGS.opensInNewTab}</span>
                  <ha-icon icon="mdi:open-in-new" aria-hidden="true"></ha-icon>
                </a>`
              : nothing}`,
          )
        : nothing}
      ${number ? row(STRINGS.trackingNumber, number) : nothing}
      ${ret.order_numbers.length ? row(STRINGS.orders, ret.order_numbers.join(", ")) : nothing}
      ${ret.items.length
        ? row(
            STRINGS.items,
            html`<ul>
              ${ret.items.map((item) => html`<li>${item}</li>`)}
            </ul>`,
          )
        : nothing}
      ${parcels.length
        ? row(
            STRINGS.returnSentBackFrom,
            html`<ul>
              ${parcels.map((parcel) => this._renderParcel(parcel))}
            </ul>`,
          )
        : nothing}
      ${ret.emails.length ? row(STRINGS.returnEmails, this._renderEmails(ret)) : nothing}
    </dl>`;
  }

  /** The parcels the items came in that this user can see. */
  private _parcels(ret: CustomerReturn): Parcel[] {
    const parcels = this.snapshot?.parcels ?? [];
    return ret.parcel_ids.flatMap((id) => parcels.find((parcel) => parcel.id === id) ?? []);
  }

  /** A parcel the items came in; a tap shows its details instead. */
  private _renderParcel(parcel: Parcel): TemplateResult {
    const name = parcelTitle(parcel);
    const when = parcel.delivered_undated
      ? STRINGS.dateNotKnownInline
      : parcel.delivered_at
        ? formatDateTime(parcel.delivered_at, this.locale)
        : "";
    const text = [statusLabel(parcel.status), when].filter(Boolean).join(" · ");
    if (parcel.restricted) {
      return html`<li>${name} · ${text}</li>`;
    }
    return html`<li>
      <button
        type="button"
        class="link-btn"
        aria-haspopup="dialog"
        aria-label=${fmt(STRINGS.showParcel, { name })}
        aria-disabled=${this._busy ? "true" : "false"}
        @click=${() => this._openParcel(parcel.id)}
      >
        ${name}</button
      > · ${text}
    </li>`;
  }

  /** The e-mails about the return, oldest first: the sender, when and how it was read. */
  private _renderEmails(ret: CustomerReturn): TemplateResult {
    const locale = this.locale;
    return html`<ul class="emails">
      ${ret.emails.map((email) => {
        const label = email.label.trim();
        const meta = [email.time ? formatDateTime(email.time, locale) : "", sourceLabel(email.source)]
          .filter(Boolean)
          .join(" · ");
        return html`<li>
          ${label ? html`<div>${label}</div>` : nothing}
          <div class="entry-meta">${meta}</div>
        </li>`;
      })}
    </ul>`;
  }

  private _renderActions(): TemplateResult {
    const busy = this._busy ? "true" : "false";
    if (this._mode === "remove") {
      return html`<div class="dialog-actions">
        <button type="button" class="btn" data-cancel @click=${this._backToView}>
          ${STRINGS.cancel}
        </button>
        <button
          type="button"
          class="btn primary danger"
          aria-disabled=${busy}
          @click=${this._remove}
        >
          ${STRINGS.removeReturn}
        </button>
      </div>`;
    }
    return html`<div class="dialog-actions" role="group" aria-label=${STRINGS.actions}>
      <span class="spacer"></span>
      <button type="button" class="btn danger" data-mode="remove" @click=${this._startRemove}>
        ${STRINGS.removeReturn}
      </button>
    </div>`;
  }

  private _startRemove(): void {
    this._mode = "remove";
    this._error = null;
    void this.focusAfterRender("[data-cancel]");
  }

  private _backToView(): void {
    this._mode = "view";
    this._error = null;
    void this.focusAfterRender('[data-mode="remove"]');
  }

  private _remove(): void {
    const hass = this.hass;
    const ret = this._return;
    if (!hass || !ret) {
      return;
    }
    void this.runAction(
      () => callParcelsCommand(hass, "return/remove", { return_id: ret.id }),
      () => this.closeDialog(),
    );
  }

  /** Closes this dialog, then asks the card to show the parcel. */
  private _openParcel(parcelId: string): void {
    if (this._busy) {
      return;
    }
    this.closeDialog();
    this.dispatchEvent(new CustomEvent<string>(OPEN_PARCEL_EVENT, { detail: parcelId }));
  }
}

defineElement("parcels-return-dialog", ParcelsReturnDialog);

declare global {
  interface HTMLElementTagNameMap {
    "parcels-return-dialog": ParcelsReturnDialog;
  }
}
