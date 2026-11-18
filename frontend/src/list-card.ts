/** parcels-list-card: active parcels that don't have a delivery date yet. */
import {
  css,
  html,
  nothing,
  type CSSResultGroup,
  type PropertyDeclarations,
  type TemplateResult,
} from "lit";
import { repeat } from "lit/directives/repeat.js";
import { ParcelsChipCard } from "./base-card.ts";
import { renderChip } from "./chip.ts";
import { cardTitle, listCardConfig, type ListCardConfig } from "./config.ts";
import { shipmentBoxes, type ShipmentBox } from "./groups.ts";
import { undatedParcels } from "./parcels.ts";
import { defineElement, registerCard } from "./register.ts";
import { STRINGS } from "./strings.ts";
import { baseStyles, chipStyles } from "./styles.ts";
import type { Snapshot } from "./types.ts";

export class ParcelsListCard extends ParcelsChipCard {
  static override properties: PropertyDeclarations = {
    _config: { state: true },
  };

  static override styles: CSSResultGroup = [
    baseStyles,
    chipStyles,
    css`
      .list {
        display: flex;
        flex-direction: column;
        gap: 6px;
        margin: 0;
        padding: 0;
        list-style: none;
      }
      .content:focus {
        outline: none;
      }
    `,
  ];

  declare private _config: ListCardConfig;

  private _listCache: { snapshot: Snapshot; boxes: ShipmentBox[] } | null = null;

  constructor() {
    super();
    this._config = listCardConfig({});
  }

  static getStubConfig(): Record<string, unknown> {
    return {};
  }

  setConfig(config: unknown): void {
    this._config = listCardConfig(config);
  }

  getCardSize(): number {
    const boxes = this._boxes();
    return boxes ? 1 + Math.max(1, boxes.length) : 3;
  }

  getGridOptions(): Record<string, unknown> {
    return { columns: 12, rows: "auto", min_columns: 6 };
  }

  protected override focusFallback(): HTMLElement | null {
    return (
      this.renderRoot.querySelector<HTMLElement>("button.chip-main") ??
      this.renderRoot.querySelector<HTMLElement>(".content")
    );
  }

  /** The undated parcels, packages of one shipment in one box. */
  private _boxes(): ShipmentBox[] | null {
    const snapshot = this.snapshot;
    if (!snapshot) {
      return null;
    }
    if (this._listCache?.snapshot !== snapshot) {
      this._listCache = { snapshot, boxes: shipmentBoxes(undatedParcels(snapshot.parcels)) };
    }
    return this._listCache.boxes;
  }

  protected override render(): TemplateResult {
    const boxes = this._boxes();
    const title = cardTitle(this._config.title, STRINGS.defaultListTitle);
    return html`<ha-card>
        ${title ? html`<div class="header"><h2 class="title">${title}</h2></div>` : nothing}
        ${this.renderBanners()}
        <div class="content" tabindex="-1">
          ${boxes ? this._renderList(boxes) : this.renderLoading()}
        </div>
      </ha-card>
      ${this.renderDetailsDialog()}`;
  }

  private _renderList(boxes: readonly ShipmentBox[]): TemplateResult {
    if (!boxes.length) {
      return html`<p class="empty">${STRINGS.noUndatedParcels}</p>`;
    }
    const locale = this.locale;
    return html`<ul class="list">
      ${repeat(
        boxes,
        (box) => box.parcel.id,
        ({ parcel, members }) =>
          html`<li>
            ${renderChip(parcel, {
              locale,
              showStatus: true,
              members,
              busy: members.some((member) => this._busyParcels.has(member.id)),
              onOpen: this.openDetails,
              onUndoMerge: this.undoMerge,
              onKeepMerge: this.keepMerge,
              onUndoInferred: this.undoInferred,
              onKeepInferred: this.keepInferred,
            })}
          </li>`,
      )}
    </ul>`;
  }
}

defineElement("parcels-list-card", ParcelsListCard);
registerCard("parcels-list-card", STRINGS.listCardName, STRINGS.listCardDescription);

declare global {
  interface HTMLElementTagNameMap {
    "parcels-list-card": ParcelsListCard;
  }
}
