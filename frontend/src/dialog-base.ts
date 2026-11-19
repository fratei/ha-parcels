/**
 * Base of the cards' modal dialogs, built on the native <dialog>: focus stays
 * inside, Esc and a click on the backdrop close it, and focus returns to the
 * element that opened it.
 */
import {
  LitElement,
  html,
  nothing,
  type PropertyDeclarations,
  type PropertyValues,
  type TemplateResult,
} from "lit";
import { errorMessage } from "./errors.ts";
import { trapFocus } from "./focus.ts";
import { STRINGS, fmt } from "./strings.ts";
import type { HomeAssistant } from "./types.ts";

/** Fired at a dialog when an action fails after the dialog was closed; detail is the message. */
export const DIALOG_ERROR_EVENT = "parcels-error";

/** Asks the card to show a parcel's details; the detail is the parcel's id. */
export const OPEN_PARCEL_EVENT = "parcels-open-parcel";

/** Asks the card to show a customer return; the detail is the return's id. */
export const OPEN_RETURN_EVENT = "parcels-open-return";

/** Moves focus back to where it was before the dialog opened. */
export type ReturnFocus = () => void;

export class ParcelsDialogBase extends LitElement {
  static override properties: PropertyDeclarations = {
    hass: { attribute: false },
    _open: { state: true },
    _busy: { state: true },
    _error: { state: true },
  };

  declare hass: HomeAssistant | undefined;
  declare protected _open: boolean;
  /** An action is running. */
  declare protected _busy: boolean;
  /** The last action error, shown inside the dialog. */
  declare protected _error: string | null;

  private _returnFocus: ReturnFocus | null = null;
  private _pressedBackdrop = false;
  private _hadFocus = false;
  /** Counts openings, so that a late result isn't shown in a later dialog. */
  private _session = 0;

  constructor() {
    super();
    this.hass = undefined;
    this._open = false;
    this._busy = false;
    this._error = null;
  }

  protected override render(): TemplateResult {
    return html`<dialog
      aria-labelledby="dialog-title"
      @close=${this._onClose}
      @keydown=${this._onKeyDown}
      @pointerdown=${this._onPointerDown}
      @click=${this._onClick}
    >
      ${this._open ? this.renderContent() : nothing}
    </dialog>`;
  }

  /** The content while open; it must contain the heading with id="dialog-title". */
  protected renderContent(): TemplateResult | typeof nothing {
    return nothing;
  }

  /** Whether a click on the backdrop may close the dialog. */
  protected canLightDismiss(): boolean {
    return !this._busy;
  }

  /** Resets the dialog's own state once it's closed. */
  protected dialogClosed(): void {}

  protected get isOpen(): boolean {
    return this._open;
  }

  protected async showDialog(returnFocus: ReturnFocus | null): Promise<void> {
    this._session += 1;
    this._returnFocus = returnFocus;
    this._open = true;
    this._busy = false;
    this._error = null;
    await this.updateComplete;
    const dialog = this._dialog();
    if (!dialog || !this._open || !this.isConnected) {
      return;
    }
    if (!dialog.open) {
      dialog.showModal();
    }
    this.focusInDialog("[data-autofocus]");
  }

  closeDialog(): void {
    const dialog = this._dialog();
    if (dialog?.open) {
      dialog.close();
    }
    this._finishClose(true);
  }

  /** Focuses the first element in the dialog that matches the selector. */
  protected focusInDialog(selector: string): void {
    this.renderRoot.querySelector<HTMLElement>(`dialog ${selector}`)?.focus();
  }

  protected async focusAfterRender(selector: string): Promise<void> {
    await this.updateComplete;
    if (this._open) {
      this.focusInDialog(selector);
    }
  }

  /**
   * Runs a service call or command: one at a time, with its error shown in the
   * dialog, or on the card when the dialog was closed in the meantime.
   */
  protected async runAction(
    action: () => Promise<unknown>,
    onSuccess?: () => void,
  ): Promise<void> {
    if (this._busy) {
      return;
    }
    const session = this._session;
    this._busy = true;
    this._error = null;
    try {
      await action();
      if (this._open && this._session === session) {
        onSuccess?.();
      }
    } catch (error) {
      const message = fmt(STRINGS.actionFailed, { message: errorMessage(error) });
      if (this._open && this._session === session) {
        this._error = message;
      } else {
        this.dispatchEvent(new CustomEvent<string>(DIALOG_ERROR_EVENT, { detail: message }));
      }
    } finally {
      if (this._session === session) {
        this._busy = false;
      }
    }
  }

  override disconnectedCallback(): void {
    super.disconnectedCallback();
    this._finishClose(false);
  }

  protected override willUpdate(_changed: PropertyValues): void {
    this._hadFocus = this._open && Boolean(this.shadowRoot?.activeElement);
  }

  protected override updated(_changed: PropertyValues): void {
    // Keep focus in the dialog when this render removed the focused element
    // (e.g. "Mark delivered" once the parcel is delivered).
    if (this._hadFocus && this._open && !this.shadowRoot?.activeElement) {
      this.focusInDialog("[data-autofocus]");
    }
    this._hadFocus = false;
  }

  private _dialog(): HTMLDialogElement | null {
    return this.renderRoot.querySelector("dialog");
  }

  private _finishClose(restoreFocus: boolean): void {
    if (!this._open) {
      return;
    }
    const returnFocus = this._returnFocus;
    this._returnFocus = null;
    this._open = false;
    this._busy = false;
    this._error = null;
    this._pressedBackdrop = false;
    this.dialogClosed();
    if (restoreFocus) {
      returnFocus?.();
    }
  }

  private _onClose(event: Event): void {
    const dialog = event.currentTarget as HTMLDialogElement;
    // Closed with Esc. Ignore a late event when the dialog was opened again.
    if (event.target === dialog && !dialog.open) {
      this._finishClose(true);
    }
  }

  private _onKeyDown(event: KeyboardEvent): void {
    trapFocus(event, event.currentTarget as HTMLElement);
  }

  private _onPointerDown(event: PointerEvent): void {
    this._pressedBackdrop = event.target === event.currentTarget;
  }

  private _onClick(event: MouseEvent): void {
    const onBackdrop = this._pressedBackdrop && event.target === event.currentTarget;
    this._pressedBackdrop = false;
    if (onBackdrop && this.canLightDismiss()) {
      this.closeDialog();
    }
  }
}
