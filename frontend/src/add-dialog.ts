/** The "Add parcel" dialog of the week card. */
import {
  css,
  html,
  nothing,
  type CSSResultGroup,
  type PropertyDeclarations,
  type TemplateResult,
} from "lit";
import { live } from "lit/directives/live.js";
import { callParcelsService } from "./api.ts";
import { carrierOptions } from "./carriers.ts";
import { ParcelsDialogBase, type ReturnFocus } from "./dialog-base.ts";
import { addFormToServiceData, type AddForm } from "./forms.ts";
import { defineElement } from "./register.ts";
import { STRINGS } from "./strings.ts";
import { baseStyles, dialogStyles } from "./styles.ts";

const EMPTY_FORM: AddForm = { tracking_number: "", carrier: "", merchant: "", private: false };

export class ParcelsAddDialog extends ParcelsDialogBase {
  static override properties: PropertyDeclarations = {
    _form: { state: true },
    _missingNumber: { state: true },
  };

  static override styles: CSSResultGroup = [
    baseStyles,
    dialogStyles,
    css`
      form {
        display: flex;
        flex-direction: column;
        gap: 12px;
        padding-top: 8px;
      }
      #tracking-number {
        font-family: var(--code-font-family, monospace);
      }
      .field-error {
        margin: 0;
        font-size: 0.8125rem;
        color: var(--error-color, #db4437);
      }
    `,
  ];

  declare private _form: AddForm;
  /** Submitted without a tracking number. */
  declare private _missingNumber: boolean;

  constructor() {
    super();
    this._form = EMPTY_FORM;
    this._missingNumber = false;
  }

  /** Opens an empty form; `returnFocus` runs when the dialog closes. */
  async open(returnFocus: ReturnFocus | null = null): Promise<void> {
    this._form = EMPTY_FORM;
    this._missingNumber = false;
    await this.showDialog(returnFocus);
  }

  /** Typed data would be lost, so a click on the backdrop doesn't close it. */
  protected override canLightDismiss(): boolean {
    return false;
  }

  protected override renderContent(): TemplateResult {
    const form = this._form;
    const missing = this._missingNumber;
    return html`
      <div class="dialog-header">
        <div class="dialog-heading">
          <h2 id="dialog-title" class="dialog-title">${STRINGS.addTitle}</h2>
        </div>
        <button
          type="button"
          class="icon-btn"
          aria-label=${STRINGS.close}
          title=${STRINGS.close}
          @click=${this.closeDialog}
        >
          <ha-icon icon="mdi:close" aria-hidden="true"></ha-icon>
        </button>
      </div>
      <div class="dialog-content">
        <form id="add-form" novalidate @submit=${this._submit}>
          <label class="field">
            <span class="field-label">${STRINGS.fieldTrackingNumber}</span>
            <input
              id="tracking-number"
              name="tracking_number"
              required
              autocomplete="off"
              autocapitalize="characters"
              spellcheck="false"
              data-autofocus
              .value=${live(form.tracking_number)}
              aria-invalid=${missing ? "true" : "false"}
              aria-describedby=${missing ? "tracking-error" : nothing}
              @input=${this._onInput}
            />
          </label>
          ${missing
            ? html`<p class="field-error" id="tracking-error">${STRINGS.trackingRequired}</p>`
            : nothing}
          <label class="field">
            <span class="field-label">${STRINGS.fieldCarrier}</span>
            <select name="carrier" @change=${this._onInput}>
              <option value="" ?selected=${form.carrier === ""}>${STRINGS.carrierAuto}</option>
              ${carrierOptions().map(
                (carrier) =>
                  html`<option value=${carrier.id} ?selected=${form.carrier === carrier.id}>
                    ${carrier.name}
                  </option>`,
              )}
            </select>
          </label>
          <label class="field">
            <span class="field-label">${STRINGS.fieldMerchant}</span>
            <input
              name="merchant"
              autocomplete="off"
              .value=${live(form.merchant)}
              @input=${this._onInput}
            />
          </label>
          <label class="check-row">
            <input
              type="checkbox"
              name="private"
              .checked=${live(form.private)}
              @change=${this._onInput}
            />
            <span>${STRINGS.fieldPrivate}</span>
          </label>
        </form>
      </div>
      ${this._error
        ? html`<div class="dialog-error">
            <div class="alert error" role="alert">
              <ha-icon icon="mdi:alert-circle-outline" aria-hidden="true"></ha-icon>
              <span class="grow">${this._error}</span>
            </div>
          </div>`
        : nothing}
      <div class="dialog-actions">
        <button type="button" class="btn" @click=${this.closeDialog}>${STRINGS.cancel}</button>
        <button
          type="submit"
          form="add-form"
          class="btn primary"
          aria-disabled=${this._busy ? "true" : "false"}
        >
          ${STRINGS.addSubmit}
        </button>
      </div>
    `;
  }

  private _onInput(event: Event): void {
    const input = event.currentTarget as HTMLInputElement | HTMLSelectElement;
    const name = input.name as keyof AddForm;
    const value =
      input instanceof HTMLInputElement && input.type === "checkbox" ? input.checked : input.value;
    this._form = { ...this._form, [name]: value };
    if (name === "tracking_number" && this._missingNumber && input.value.trim()) {
      this._missingNumber = false;
    }
  }

  private _submit(event: Event): void {
    event.preventDefault();
    const hass = this.hass;
    if (!hass || this._busy) {
      return;
    }
    const data = addFormToServiceData(this._form);
    if (!data) {
      this._missingNumber = true;
      void this.focusAfterRender("#tracking-number");
      return;
    }
    void this.runAction(
      () => callParcelsService(hass, "add", data),
      () => this.closeDialog(),
    );
  }
}

defineElement("parcels-add-dialog", ParcelsAddDialog);

declare global {
  interface HTMLElementTagNameMap {
    "parcels-add-dialog": ParcelsAddDialog;
  }
}
