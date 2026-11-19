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
import { FILTER_LABELS, type ParcelFilter } from "./filter.ts";
import { shipmentBoxes, type ShipmentBox } from "./groups.ts";
import { undatedParcels } from "./parcels.ts";
import { defineElement, registerCard } from "./register.ts";
import { STRINGS, fmt } from "./strings.ts";
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
      .filter-note {
        margin: 0 0 8px;
        font-size: 0.875rem;
        color: var(--secondary-text-color, #727272);
      }
    `,
  ];

  declare private _config: ListCardConfig;

  private _listCache: {
    snapshot: Snapshot;
    filter: ParcelFilter;
    boxes: ShipmentBox[];
    /** Undated parcels the filter hides. */
    hidden: number;
  } | null = null;

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
    const boxes = this._list()?.boxes;
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

  /** The undated parcels the filter shows, packages of one shipment in one box. */
  private _list(): { boxes: ShipmentBox[]; hidden: number } | null {
    const snapshot = this.snapshot;
    if (!snapshot) {
      return null;
    }
    const filter = this._filter;
    const cache = this._listCache;
    if (cache?.snapshot === snapshot && cache.filter === filter) {
      return cache;
    }
    const undated = undatedParcels(snapshot.parcels);
    const shown = this.filterParcels(snapshot, undated);
    this._listCache = {
      snapshot,
      filter,
      boxes: shipmentBoxes(shown),
      hidden: undated.length - shown.length,
    };
    return this._listCache;
  }

  protected override render(): TemplateResult {
    const list = this._list();
    const title = cardTitle(this._config.title, STRINGS.defaultListTitle);
    return html`<ha-card>
        ${title ? html`<div class="header"><h2 class="title">${title}</h2></div>` : nothing}
        ${this.renderBanners()}
        <div class="content" tabindex="-1">
          ${list ? this._renderList(list.boxes, list.hidden) : this.renderLoading()}
        </div>
      </ha-card>
      ${this.renderDetailsDialog()}`;
  }

  /** "Filter: Active · Show all", while the filter hides some of these parcels. */
  private _renderFilterNote(hidden: number): TemplateResult | typeof nothing {
    if (hidden === 0 || this._filter === "all") {
      return nothing;
    }
    return html`<p class="filter-note">
      ${fmt(STRINGS.filterNote, { filter: FILTER_LABELS[this._filter] })} ·
      <button type="button" class="link-btn" @click=${this._showAll}>${STRINGS.filterShowAll}</button>
    </p>`;
  }

  private readonly _showAll = (): void => {
    this.setFilter("all");
  };

  private _renderList(boxes: readonly ShipmentBox[], hidden: number): TemplateResult {
    if (!boxes.length) {
      return html`${this._renderFilterNote(hidden)}
        <p class="empty">${hidden > 0 ? STRINGS.noUndatedMatch : STRINGS.noUndatedParcels}</p>`;
    }
    const locale = this.locale;
    return html`${this._renderFilterNote(hidden)}
      <ul class="list">
      ${repeat(
        boxes,
        (box) => box.parcel.id,
        ({ parcel, members }) =>
          html`<li>
            ${renderChip(parcel, {
              locale,
              showStatus: true,
              members,
              possibly: this.possiblyFor(members),
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
