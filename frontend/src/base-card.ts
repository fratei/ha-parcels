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
import { chipSelector, returnChipSelector } from "./chip.ts";
import { possiblyLine } from "./describe.ts";
import "./details-dialog.ts";
import type { ParcelsDetailsDialog } from "./details-dialog.ts";
import { errorMessage } from "./errors.ts";
import {
  FILTER_EVENT,
  FILTER_KEY,
  isParcelFilter,
  matchesFilter,
  matchesReturnFilter,
  readFilter,
  saveFilter,
  type ParcelFilter,
} from "./filter.ts";
import { localeOptions, type LocaleOptions } from "./format.ts";
import { suggestedCandidates } from "./parcels.ts";
import "./return-dialog.ts";
import type { ParcelsReturnDialog } from "./return-dialog.ts";
import { SnapshotController } from "./snapshot-controller.ts";
import { STRINGS, fmt } from "./strings.ts";
import type { CustomerReturn, HomeAssistant, Parcel, Snapshot } from "./types.ts";

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

/**
 * A card that shows parcel chips, which open the details dialog, under the
 * parcel filter chosen on this device (shared by the cards on the page).
 */
export abstract class ParcelsChipCard extends ParcelsCardBase {
  static override properties: PropertyDeclarations = {
    _busyParcels: { state: true },
    _filter: { state: true },
  };

  /** Parcels with an Undo or Keep running. */
  declare protected _busyParcels: ReadonlySet<string>;
  declare protected _filter: ParcelFilter;

  /** The parcel whose chip had focus before the current render. */
  private _focusedParcel: string | null = null;
  /** The customer return whose chip had focus before the current render. */
  private _focusedReturn: string | null = null;

  constructor() {
    super();
    this._busyParcels = new Set();
    this._filter = readFilter();
  }

  override connectedCallback(): void {
    super.connectedCallback();
    this._filter = readFilter();
    window.addEventListener(FILTER_EVENT, this._onFilterEvent);
    window.addEventListener("storage", this._onStorage);
  }

  override disconnectedCallback(): void {
    super.disconnectedCallback();
    window.removeEventListener(FILTER_EVENT, this._onFilterEvent);
    window.removeEventListener("storage", this._onStorage);
  }

  /** Chooses the filter for every card on this device. */
  protected setFilter(filter: ParcelFilter): void {
    this._filter = filter;
    saveFilter(filter);
  }

  /** The parcels the chosen filter shows. */
  protected filterParcels(snapshot: Snapshot, parcels: readonly Parcel[]): readonly Parcel[] {
    const filter = this._filter;
    if (filter === "all") {
      return parcels;
    }
    const context = { today: snapshot.settings.today, timeZone: snapshot.settings.time_zone };
    return parcels.filter((parcel) => matchesFilter(parcel, filter, context));
  }

  /** The customer returns the chosen filter shows. */
  protected filterReturns(
    snapshot: Snapshot,
    returns: readonly CustomerReturn[],
  ): readonly CustomerReturn[] {
    const filter = this._filter;
    if (filter === "all") {
      return returns;
    }
    const context = { today: snapshot.settings.today };
    return returns.filter((ret) => matchesReturnFilter(ret, filter, context));
  }

  private _candidates: { snapshot: Snapshot; map: Map<string, Parcel[]> } | null = null;

  /**
   * "Possibly: …" for a box whose items aren't known, from the merge
   * suggestions about its packages (only administrators get suggestions).
   */
  protected possiblyFor(members: readonly Parcel[]): string | null {
    const snapshot = this.snapshot;
    if (!snapshot) {
      return null;
    }
    if (this._candidates?.snapshot !== snapshot) {
      this._candidates = { snapshot, map: suggestedCandidates(snapshot.merge_suggestions) };
    }
    const map = this._candidates.map;
    const ids = new Set(members.map((member) => member.id));
    const candidates = new Map<string, Parcel>();
    for (const member of members) {
      for (const candidate of map.get(member.id) ?? []) {
        if (!ids.has(candidate.id)) {
          candidates.set(candidate.id, candidate);
        }
      }
    }
    return candidates.size ? possiblyLine([...candidates.values()]) : null;
  }

  private readonly _onFilterEvent = (event: Event): void => {
    const filter = (event as CustomEvent<unknown>).detail;
    if (isParcelFilter(filter)) {
      this._filter = filter;
    }
  };

  /** Another tab of this browser chose a filter. */
  private readonly _onStorage = (event: StorageEvent): void => {
    if (event.key === null || event.key === FILTER_KEY) {
      this._filter = readFilter();
    }
  };

  protected override willUpdate(changed: PropertyValues): void {
    super.willUpdate(changed);
    const active = this.shadowRoot?.activeElement;
    const chip = active instanceof HTMLElement ? active.closest<HTMLElement>(".chip") : null;
    this._focusedParcel = chip?.dataset.parcelId ?? null;
    this._focusedReturn = chip?.dataset.returnId ?? null;
  }

  protected override updated(changed: PropertyValues): void {
    super.updated(changed);
    // Moving or replacing a chip drops its focus; give it back to the same parcel or return.
    const parcelId = this._focusedParcel;
    const returnId = this._focusedReturn;
    this._focusedParcel = null;
    this._focusedReturn = null;
    if (this.shadowRoot?.activeElement || !focusIsLost()) {
      return;
    }
    const selector =
      parcelId !== null ? chipSelector(parcelId) : returnId !== null ? returnChipSelector(returnId) : null;
    if (selector) {
      this.renderRoot.querySelector<HTMLElement>(selector)?.focus();
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

  protected readonly openReturn = (ret: CustomerReturn, opener: HTMLElement): void => {
    const dialog = this.renderRoot.querySelector<ParcelsReturnDialog>("parcels-return-dialog");
    void dialog?.open(ret.id, () => {
      const target = opener.isConnected
        ? opener
        : (this.renderRoot.querySelector<HTMLElement>(returnChipSelector(ret.id)) ??
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

  protected readonly undoInferred = (parcel: Parcel): void => {
    void this._parcelAction(
      parcel.id,
      "undo_delivery",
      { parcel_id: parcel.id },
      STRINGS.undoInferredFailed,
    );
  };

  protected readonly keepInferred = (parcel: Parcel): void => {
    void this._parcelAction(
      parcel.id,
      "update",
      { parcel_id: parcel.id, confirm_delivery: true },
      STRINGS.keepInferredFailed,
    );
  };

  protected renderDetailsDialog(): TemplateResult {
    return html`<parcels-details-dialog
      .hass=${this.hass}
      .snapshot=${this.snapshot}
      .locale=${this.locale}
      @parcels-error=${this._onDialogError}
      @parcels-open-return=${this._onOpenReturn}
    ></parcels-details-dialog>`;
  }

  protected renderReturnDialog(): TemplateResult {
    return html`<parcels-return-dialog
      .hass=${this.hass}
      .snapshot=${this.snapshot}
      .locale=${this.locale}
      @parcels-error=${this._onDialogError}
      @parcels-open-parcel=${this._onOpenParcel}
    ></parcels-return-dialog>`;
  }

  /**
   * One dialog asked for another: the first has closed and given focus back
   * to its chip, which the second gives focus back to in turn.
   */
  private _opener(): HTMLElement | null {
    const active = this.shadowRoot?.activeElement;
    return active instanceof HTMLElement ? active : this.focusFallback();
  }

  private _onOpenParcel(event: CustomEvent<string>): void {
    const parcel = this.snapshot?.parcels.find((item) => item.id === event.detail);
    const opener = this._opener();
    if (parcel && opener) {
      this.openDetails(parcel, opener);
    }
  }

  private _onOpenReturn(event: CustomEvent<string>): void {
    const ret = this.snapshot?.returns.find((item) => item.id === event.detail);
    const opener = this._opener();
    if (ret && opener) {
      this.openReturn(ret, opener);
    }
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
