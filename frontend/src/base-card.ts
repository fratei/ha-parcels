/** What the three cards share: the hass object, the shared snapshot, locale and error banners. */
import {
  LitElement,
  html,
  nothing,
  type PropertyDeclarations,
  type PropertyValues,
  type TemplateResult,
} from "lit";
import { callParcelsService } from "./api.ts";
import { chipSelector } from "./chip.ts";
import "./details-dialog.ts";
import type { ParcelsDetailsDialog } from "./details-dialog.ts";
import { errorMessage } from "./errors.ts";
import { localeOptions, type LocaleOptions } from "./format.ts";
import { SnapshotController } from "./snapshot-controller.ts";
import { STRINGS, fmt } from "./strings.ts";
import type { HomeAssistant, Parcel, Snapshot } from "./types.ts";

export abstract class ParcelsCardBase extends LitElement {
  static override properties: PropertyDeclarations = {
    _actionError: { state: true },
  };

  /** The last failed action, shown until dismissed or the next action. */
  declare protected _actionError: string | null;

  protected readonly _snapshots = new SnapshotController(this);
  private _hass: HomeAssistant | undefined = undefined;
  private _hassKey: string | null = null;
  private _locale: LocaleOptions | null = null;
  private _localeKey = "";

  constructor() {
    super();
    this._actionError = null;
  }

  get hass(): HomeAssistant | undefined {
    return this._hass;
  }

  /**
   * Home Assistant sets a new hass object on every state change; only the
   * parts the cards use (connection, language, time zone, admin, theme)
   * cause a render.
   */
  set hass(hass: HomeAssistant | undefined) {
    this._hass = hass;
    this._snapshots.setConnection(hass?.connection ?? null);
    this.toggleAttribute("dark", hass?.themes?.darkMode === true);
    const key = JSON.stringify([
      hass?.language,
      hass?.locale?.language,
      hass?.locale?.time_format,
      hass?.locale?.time_zone,
      hass?.config?.time_zone,
      hass?.user?.is_admin,
      hass?.themes?.darkMode,
    ]);
    if (key !== this._hassKey) {
      this._hassKey = key;
      this.requestUpdate();
    }
    this.hassChanged();
  }

  /** Called after every hass update. */
  protected hassChanged(): void {}

  protected get snapshot(): Snapshot | null {
    return this._snapshots.snapshot;
  }

  /** Language, 12/24 h and time zone for formatting. */
  protected get locale(): LocaleOptions {
    const serverTimeZone = this._snapshots.snapshot?.settings.time_zone;
    const key = `${this._hassKey ?? ""}|${serverTimeZone ?? ""}`;
    if (!this._locale || key !== this._localeKey) {
      this._locale = localeOptions(this._hass, serverTimeZone);
      this._localeKey = key;
    }
    return this._locale;
  }

  /** Calls a parcels service; on failure shows `failure` (with the error message) on the card. */
  protected async callService(
    service: string,
    data: Record<string, unknown>,
    failure: string,
  ): Promise<boolean> {
    const hass = this._hass;
    if (!hass) {
      return false;
    }
    this._actionError = null;
    try {
      await callParcelsService(hass, service, data);
      return true;
    } catch (error) {
      this._actionError = fmt(failure, { message: errorMessage(error) });
      return false;
    }
  }

  protected renderBanners(): TemplateResult | typeof nothing {
    const { snapshot, error } = this._snapshots;
    if (!error && !this._actionError) {
      return nothing;
    }
    return html`<div class="banners">
      ${error
        ? html`<div class="alert ${snapshot ? "warning" : "error"}" role="alert">
            <ha-icon icon="mdi:alert-circle-outline" aria-hidden="true"></ha-icon>
            <span class="grow">
              ${fmt(snapshot ? STRINGS.refreshError : STRINGS.loadError, { message: error })}
            </span>
          </div>`
        : nothing}
      ${this._actionError
        ? html`<div class="alert error" role="alert">
            <ha-icon icon="mdi:alert-circle-outline" aria-hidden="true"></ha-icon>
            <span class="grow">${this._actionError}</span>
            <button
              type="button"
              class="icon-btn"
              aria-label=${STRINGS.dismissMessage}
              title=${STRINGS.dismissMessage}
              @click=${this._dismissActionError}
            >
              <ha-icon icon="mdi:close" aria-hidden="true"></ha-icon>
            </button>
          </div>`
        : nothing}
    </div>`;
  }

  protected renderLoading(): TemplateResult | typeof nothing {
    if (this._snapshots.error) {
      return nothing;
    }
    return html`<p class="empty" role="status">${STRINGS.loading}</p>`;
  }

  protected showActionError(message: string): void {
    this._actionError = message;
  }

  private _dismissActionError(): void {
    this._actionError = null;
  }
}

/** A card that shows parcel chips, which open the details dialog. */
export abstract class ParcelsChipCard extends ParcelsCardBase {
  static override properties: PropertyDeclarations = {
    _busyParcels: { state: true },
  };

  /** Parcels with an Undo or Keep running. */
  declare protected _busyParcels: ReadonlySet<string>;

  /** The parcel whose chip had focus before the current render. */
  private _focusedParcel: string | null = null;

  constructor() {
    super();
    this._busyParcels = new Set();
  }

  protected override willUpdate(changed: PropertyValues): void {
    super.willUpdate(changed);
    const active = this.shadowRoot?.activeElement;
    this._focusedParcel =
      active instanceof HTMLElement
        ? (active.closest<HTMLElement>(".chip[data-parcel-id]")?.dataset.parcelId ?? null)
        : null;
  }

  protected override updated(changed: PropertyValues): void {
    super.updated(changed);
    // Moving or replacing a chip drops its focus; give it back to the same parcel.
    const parcelId = this._focusedParcel;
    this._focusedParcel = null;
    if (parcelId !== null && !this.shadowRoot?.activeElement && focusIsLost()) {
      this.renderRoot.querySelector<HTMLElement>(chipSelector(parcelId))?.focus();
    }
  }

  /** Where focus goes when the parcel of a closed dialog is gone. */
  protected focusFallback(): HTMLElement | null {
    return this.renderRoot.querySelector<HTMLElement>("[data-focus-fallback], button.chip-main");
  }

  protected readonly openDetails = (parcel: Parcel, opener: HTMLElement): void => {
    const dialog = this.renderRoot.querySelector<ParcelsDetailsDialog>("parcels-details-dialog");
    void dialog?.open(parcel.id, () => {
      const target = opener.isConnected
        ? opener
        : (this.renderRoot.querySelector<HTMLElement>(chipSelector(parcel.id)) ??
          this.focusFallback());
      target?.focus();
    });
  };

  protected readonly undoMerge = (parcel: Parcel): void => {
    void this._parcelAction(parcel.id, "undo_merge", { parcel_id: parcel.id }, STRINGS.undoFailed);
  };

  protected readonly keepMerge = (parcel: Parcel): void => {
    void this._parcelAction(
      parcel.id,
      "update",
      { parcel_id: parcel.id, confirm_merge: true },
      STRINGS.keepFailed,
    );
  };

  protected renderDetailsDialog(): TemplateResult {
    return html`<parcels-details-dialog
      .hass=${this.hass}
      .snapshot=${this.snapshot}
      .locale=${this.locale}
      @parcels-error=${this._onDialogError}
    ></parcels-details-dialog>`;
  }

  private async _parcelAction(
    parcelId: string,
    service: string,
    data: Record<string, unknown>,
    failure: string,
  ): Promise<void> {
    if (this._busyParcels.has(parcelId)) {
      return;
    }
    this._busyParcels = new Set([...this._busyParcels, parcelId]);
    try {
      await this.callService(service, data, failure);
    } finally {
      const busy = new Set(this._busyParcels);
      busy.delete(parcelId);
      this._busyParcels = busy;
    }
  }

  private _onDialogError(event: CustomEvent<string>): void {
    this.showActionError(event.detail);
  }
}

/** True when nothing has focus, e.g. after the focused element was removed. */
export function focusIsLost(): boolean {
  const active = document.activeElement;
  return !active || active === document.body;
}
