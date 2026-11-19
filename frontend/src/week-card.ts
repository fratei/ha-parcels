/** parcels-week-card: a Monday to Sunday calendar of parcel deliveries. */
import {
  css,
  html,
  nothing,
  type CSSResultGroup,
  type PropertyDeclarations,
  type PropertyValues,
  type TemplateResult,
} from "lit";
import { repeat } from "lit/directives/repeat.js";
import { styleMap } from "lit/directives/style-map.js";
import "./add-dialog.ts";
import type { ParcelsAddDialog } from "./add-dialog.ts";
import { ParcelsChipCard } from "./base-card.ts";
import { renderChip } from "./chip.ts";
import { cardTitle, weekCardConfig, type WeekCardConfig } from "./config.ts";
import { addDays, startOfWeek } from "./dates.ts";
import { FILTER_LABELS, PARCEL_FILTERS, type ParcelFilter } from "./filter.ts";
import { RANGE_FORMAT, formatDate, formatDateRange } from "./format.ts";
import { layoutWeek, type WeekItem, type WeekLayout } from "./placement.ts";
import { defineElement, registerCard } from "./register.ts";
import { STRINGS, fmt } from "./strings.ts";
import { baseStyles, chipStyles } from "./styles.ts";
import type { Snapshot } from "./types.ts";

/** Below this card width the days are stacked; back side by side from WIDE_FROM. */
const NARROW_BELOW = 600;
const WIDE_FROM = 616;

const DAY_SHORT: Intl.DateTimeFormatOptions = { weekday: "short" };
const DAY_NUMBER: Intl.DateTimeFormatOptions = { day: "numeric" };
const DAY_LONG: Intl.DateTimeFormatOptions = { weekday: "long", day: "numeric", month: "long" };
const DAY_STACKED: Intl.DateTimeFormatOptions = { weekday: "long", day: "numeric", month: "short" };

export class ParcelsWeekCard extends ParcelsChipCard {
  static override properties: PropertyDeclarations = {
    _config: { state: true },
    _weekOffset: { state: true },
    _narrow: { state: true },
    _refreshing: { state: true },
  };

  static override styles: CSSResultGroup = [
    baseStyles,
    chipStyles,
    css`
      .heading {
        flex: 1 1 12rem;
        min-width: 0;
      }
      .range {
        margin: 0;
        font-size: 0.875rem;
        color: var(--secondary-text-color, #727272);
      }
      .title + .range {
        margin-top: 2px;
      }
      .controls {
        display: flex;
        flex-wrap: wrap;
        align-items: center;
        gap: 4px 8px;
      }
      .nav {
        display: flex;
        align-items: center;
        gap: 2px;
      }
      .spin {
        animation: spin 1s linear infinite;
      }
      @keyframes spin {
        to {
          transform: rotate(360deg);
        }
      }
      @media (prefers-reduced-motion: reduce) {
        .spin {
          animation: none;
        }
      }

      .grid {
        display: grid;
        row-gap: 6px;
        padding: 4px 12px 16px;
      }
      .day-bg {
        grid-row: 1 / -1;
        border-inline-start: 1px solid var(--divider-color, rgba(0, 0, 0, 0.12));
      }
      .day-bg:first-child {
        border-inline-start-color: transparent;
      }
      .day-bg.today {
        border-radius: 8px;
        background: color-mix(in srgb, var(--primary-color, #03a9f4) 8%, transparent);
      }
      .day-head {
        grid-row: 1;
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 2px;
        min-width: 0;
        padding: 6px 0 2px;
        font-size: 0.75rem;
        color: var(--secondary-text-color, #727272);
      }
      .day-head .dow {
        max-width: 100%;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }
      .day-head .dom {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        min-width: 28px;
        height: 28px;
        border-radius: 14px;
        color: var(--primary-text-color, #212121);
        font-size: 0.9375rem;
        font-weight: 500;
      }
      .day-head.today .dow {
        color: var(--primary-color, #03a9f4);
        font-weight: 600;
      }
      .day-head.today .dom {
        background: var(--primary-color, #03a9f4);
        color: var(--text-primary-color, #fff);
      }
      .grid .chip {
        align-self: start;
        margin: 0 3px;
      }
      .grid .chip.cont-before {
        margin-inline-start: 0;
      }
      .grid .chip.cont-after {
        margin-inline-end: 0;
      }
      .week-empty {
        grid-column: 1 / -1;
        grid-row: 2;
        margin: 0;
        padding: 16px 0;
        color: var(--secondary-text-color, #727272);
        text-align: center;
      }
      .week-empty.stacked {
        padding: 8px 16px;
      }
      .filters {
        display: flex;
        flex-wrap: wrap;
        gap: 6px;
        padding: 0 16px 8px;
      }
      .filter-btn {
        min-height: 32px;
        padding: 0 12px;
        border: 1px solid var(--divider-color, rgba(0, 0, 0, 0.12));
        border-radius: 16px;
        background: transparent;
        color: var(--primary-text-color, #212121);
        font-size: 0.8125rem;
        font-weight: 500;
        cursor: pointer;
      }
      .filter-btn:hover {
        background: color-mix(in srgb, var(--primary-color, #03a9f4) 8%, transparent);
      }
      .filter-btn[aria-pressed="true"] {
        border-color: transparent;
        background: color-mix(in srgb, var(--primary-color, #03a9f4) 18%, transparent);
        color: var(--primary-color, #03a9f4);
      }

      .days {
        display: flex;
        flex-direction: column;
        gap: 2px;
        margin: 0;
        padding: 4px 12px 16px;
        list-style: none;
      }
      .day {
        display: flex;
        flex-direction: column;
        gap: 6px;
        padding: 8px;
        border-radius: 8px;
      }
      .day.compact {
        flex-direction: row;
        flex-wrap: wrap;
        align-items: baseline;
        gap: 2px 8px;
        padding: 4px 8px;
      }
      .day.today {
        background: color-mix(in srgb, var(--primary-color, #03a9f4) 8%, transparent);
      }
      .day-label {
        display: flex;
        align-items: center;
        gap: 6px;
        margin: 0;
        font-size: 0.875rem;
        font-weight: 500;
      }
      .day.compact .day-label {
        font-weight: 400;
        color: var(--secondary-text-color, #727272);
      }
      .day.compact .muted {
        font-size: 0.8125rem;
      }
      .day.today .day-label {
        color: var(--primary-color, #03a9f4);
      }
      .day-chips {
        display: flex;
        flex-direction: column;
        gap: 6px;
        margin: 0;
        padding: 0;
        list-style: none;
      }
    `,
  ];

  declare private _config: WeekCardConfig;
  /** Weeks before (negative) or after the current one. */
  declare private _weekOffset: number;
  /** The days are stacked because the card is narrow. */
  declare private _narrow: boolean;
  declare private _refreshing: boolean;

  private _resizeObserver: ResizeObserver | null = null;
  private _resizeFrame = 0;
  private _layoutCache: {
    snapshot: Snapshot;
    monday: string;
    showArchived: boolean;
    filter: ParcelFilter;
    layout: WeekLayout;
  } | null = null;

  constructor() {
    super();
    this._config = weekCardConfig({});
    this._weekOffset = 0;
    this._narrow = false;
    this._refreshing = false;
  }

  static getStubConfig(): Record<string, unknown> {
    return {};
  }

  setConfig(config: unknown): void {
    this._config = weekCardConfig(config);
  }

  getCardSize(): number {
    const layout = this._layout();
    if (!layout) {
      return 4;
    }
    if (this._narrow) {
      const chips = layout.perDay.reduce((total, items) => total + items.length, 0);
      return 2 + 7 + chips;
    }
    return 3 + Math.max(1, layout.lanes);
  }

  getGridOptions(): Record<string, unknown> {
    return { columns: "full", rows: "auto", min_columns: 6 };
  }

  override connectedCallback(): void {
    super.connectedCallback();
    if (typeof ResizeObserver !== "undefined") {
      this._resizeObserver ??= new ResizeObserver((entries) => {
        const width = entries[entries.length - 1]?.contentRect.width ?? 0;
        // Not in the observer callback, to avoid "ResizeObserver loop" errors.
        cancelAnimationFrame(this._resizeFrame);
        this._resizeFrame = requestAnimationFrame(() => this._measure(width));
      });
      this._resizeObserver.observe(this);
    }
  }

  override disconnectedCallback(): void {
    super.disconnectedCallback();
    this._resizeObserver?.disconnect();
    cancelAnimationFrame(this._resizeFrame);
  }

  protected override firstUpdated(changed: PropertyValues): void {
    super.firstUpdated(changed);
    this._measure(this.getBoundingClientRect().width);
  }

  protected override focusFallback(): HTMLElement | null {
    return this.renderRoot.querySelector<HTMLElement>("[data-focus-fallback]");
  }

  private _measure(width: number): void {
    if (width <= 0) {
      return;
    }
    if (width < NARROW_BELOW) {
      this._narrow = true;
    } else if (width >= WIDE_FROM) {
      this._narrow = false;
    }
  }

  private _monday(snapshot: Snapshot): string {
    return addDays(startOfWeek(snapshot.settings.today), 7 * this._weekOffset);
  }

  private _layout(): WeekLayout | null {
    const snapshot = this.snapshot;
    if (!snapshot) {
      return null;
    }
    const monday = this._monday(snapshot);
    const showArchived = this._config.show_archived;
    const filter = this._filter;
    const cache = this._layoutCache;
    if (
      cache &&
      cache.snapshot === snapshot &&
      cache.monday === monday &&
      cache.showArchived === showArchived &&
      cache.filter === filter
    ) {
      return cache.layout;
    }
    const layout = layoutWeek(
      this.filterParcels(snapshot, snapshot.parcels),
      monday,
      { today: snapshot.settings.today, timeZone: snapshot.settings.time_zone },
      { showArchived },
    );
    this._layoutCache = { snapshot, monday, showArchived, filter, layout };
    return layout;
  }

  protected override render(): TemplateResult {
    const snapshot = this.snapshot;
    const layout = this._layout();
    const title = cardTitle(this._config.title, STRINGS.defaultWeekTitle);
    const range = layout ? formatDateRange(layout.start, layout.end, this.locale, RANGE_FORMAT) : "";
    return html`<ha-card>
        <div class="header">
          <div class="heading">
            ${title ? html`<h2 class="title">${title}</h2>` : nothing}
            ${range ? html`<p class="range" aria-live="polite">${range}</p>` : nothing}
          </div>
          <div class="controls">
            <div class="nav" role="group" aria-label=${STRINGS.weekNavigation}>
              <button
                type="button"
                class="icon-btn"
                aria-label=${STRINGS.previousWeek}
                title=${STRINGS.previousWeek}
                @click=${this._previousWeek}
              >
                <ha-icon class="flip" icon="mdi:chevron-left" aria-hidden="true"></ha-icon>
              </button>
              <button type="button" class="btn" title=${STRINGS.goToToday} @click=${this._thisWeek}>
                ${STRINGS.today}
              </button>
              <button
                type="button"
                class="icon-btn"
                aria-label=${STRINGS.nextWeek}
                title=${STRINGS.nextWeek}
                @click=${this._nextWeek}
              >
                <ha-icon class="flip" icon="mdi:chevron-right" aria-hidden="true"></ha-icon>
              </button>
            </div>
            <button
              type="button"
              class="icon-btn"
              aria-label=${STRINGS.refresh}
              title=${STRINGS.refresh}
              aria-disabled=${this._refreshing ? "true" : "false"}
              @click=${this._refresh}
            >
              <ha-icon
                class=${this._refreshing ? "spin" : ""}
                icon="mdi:refresh"
                aria-hidden="true"
              ></ha-icon>
            </button>
            <button type="button" class="btn" data-focus-fallback @click=${this._openAdd}>
              <ha-icon icon="mdi:plus" aria-hidden="true"></ha-icon>${STRINGS.addParcel}
            </button>
          </div>
        </div>
        ${this._renderFilters()} ${this.renderBanners()}
        ${snapshot && layout
          ? this._narrow
            ? this._renderStacked(snapshot, layout, range)
            : this._renderGrid(snapshot, layout, range)
          : html`<div class="content">${this.renderLoading()}</div>`}
      </ha-card>
      ${this.renderDetailsDialog()}
      <parcels-add-dialog
        .hass=${this.hass}
        @parcels-error=${this._onAddError}
      ></parcels-add-dialog>`;
  }

  private _renderGrid(snapshot: Snapshot, layout: WeekLayout, range: string): TemplateResult {
    const locale = this.locale;
    const today = snapshot.settings.today;
    const empty = layout.items.length === 0;
    const columns = layout.busy
      .map((busy) => (busy || empty ? "minmax(0, 1fr)" : "minmax(0, 0.6fr)"))
      .join(" ");
    const gridStyle = {
      "grid-template-columns": columns,
      "grid-template-rows": `auto repeat(${Math.max(1, layout.lanes)}, auto)`,
    };
    return html`<div
      class="grid"
      role="group"
      aria-label=${fmt(STRINGS.weekOf, { range })}
      style=${styleMap(gridStyle)}
    >
      ${layout.days.map(
        (day, column) =>
          html`<div
            class="day-bg ${day === today ? "today" : ""}"
            style=${styleMap({ "grid-column": String(column + 1) })}
            aria-hidden="true"
          ></div>`,
      )}
      ${layout.days.map(
        (day, column) =>
          html`<div
            class="day-head ${day === today ? "today" : ""}"
            style=${styleMap({ "grid-column": String(column + 1) })}
            aria-current=${day === today ? "date" : nothing}
          >
            <span class="dow" aria-hidden="true">${formatDate(day, locale, DAY_SHORT)}</span>
            <span class="dom" aria-hidden="true">${formatDate(day, locale, DAY_NUMBER)}</span>
            <span class="sr-only">${formatDate(day, locale, DAY_LONG)}</span>
          </div>`,
      )}
      ${empty ? html`<p class="week-empty">${this._emptyText()}</p>` : nothing}
      ${repeat(
        layout.items,
        (item) => item.parcel.id,
        (item) => this._chip(item, false, {
          "grid-column": `${item.startCol + 1} / ${item.endCol + 2}`,
          "grid-row": String(item.lane + 2),
        }),
      )}
    </div>`;
  }

  private _renderStacked(snapshot: Snapshot, layout: WeekLayout, range: string): TemplateResult {
    const locale = this.locale;
    const today = snapshot.settings.today;
    const filteredOut = this._filter !== "all" && layout.items.length === 0;
    return html`${filteredOut ? html`<p class="week-empty stacked">${this._emptyText()}</p>` : nothing}
      <ol class="days" aria-label=${fmt(STRINGS.weekOf, { range })}>
      ${layout.days.map((day, column) => {
        const items = layout.perDay[column] ?? [];
        const isToday = day === today;
        return html`<li
          class="day ${items.length ? "" : "compact"} ${isToday ? "today" : ""}"
          aria-current=${isToday ? "date" : nothing}
        >
          <p class="day-label">
            ${formatDate(day, locale, DAY_STACKED)}${isToday
              ? html`<span class="badge info">${STRINGS.todayTag}</span>`
              : nothing}
          </p>
          ${items.length
            ? html`<ul class="day-chips">
                ${repeat(
                  items,
                  (item) => item.parcel.id,
                  (item) => html`<li>${this._chip(item, true, undefined, column)}</li>`,
                )}
              </ul>`
            : html`<span class="muted">${STRINGS.noDeliveriesThisDay}</span>`}
        </li>`;
      })}
    </ol>`;
  }

  /**
   * A chip in the grid (one per parcel or shipment box, spanning its days) or
   * in a stacked day (one per day; the continuation marks only on its first and
   * last day).
   */
  private _chip(
    item: WeekItem,
    stacked: boolean,
    position?: Record<string, string>,
    column?: number,
  ): TemplateResult {
    const continuesBefore = item.continuesBefore && (!stacked || column === item.startCol);
    const continuesAfter = item.continuesAfter && (!stacked || column === item.endCol);
    return renderChip(item.parcel, {
      locale: this.locale,
      placement: item.placement,
      continuesBefore,
      continuesAfter,
      showRange: stacked,
      members: item.members,
      possibly: this.possiblyFor(item.members),
      busy: item.members.some((member) => this._busyParcels.has(member.id)),
      position,
      onOpen: this.openDetails,
      onUndoMerge: this.undoMerge,
      onKeepMerge: this.keepMerge,
      onUndoInferred: this.undoInferred,
      onKeepInferred: this.keepInferred,
    });
  }

  /** All, Active, Recent or Completed; the choice is kept on this device. */
  private _renderFilters(): TemplateResult {
    return html`<div class="filters" role="group" aria-label=${STRINGS.filterLabel}>
      ${PARCEL_FILTERS.map(
        (filter) =>
          html`<button
            type="button"
            class="filter-btn"
            aria-pressed=${this._filter === filter ? "true" : "false"}
            title=${filter === "recent" ? STRINGS.filterRecentHint : nothing}
            @click=${() => this.setFilter(filter)}
          >
            ${FILTER_LABELS[filter]}
          </button>`,
      )}
    </div>`;
  }

  private _emptyText(): string {
    return this._filter === "all" ? STRINGS.noDeliveriesThisWeek : STRINGS.filterEmptyWeek;
  }

  private _previousWeek(): void {
    this._weekOffset -= 1;
  }

  private _nextWeek(): void {
    this._weekOffset += 1;
  }

  private _thisWeek(): void {
    this._weekOffset = 0;
  }

  private async _refresh(): Promise<void> {
    if (this._refreshing) {
      return;
    }
    this._refreshing = true;
    try {
      await this.callService("refresh", {}, STRINGS.refreshFailed);
    } finally {
      this._refreshing = false;
    }
  }

  private _openAdd(event: MouseEvent): void {
    const button = event.currentTarget as HTMLElement;
    const dialog = this.renderRoot.querySelector<ParcelsAddDialog>("parcels-add-dialog");
    void dialog?.open(() => {
      if (button.isConnected) {
        button.focus();
      }
    });
  }

  private _onAddError(event: CustomEvent<string>): void {
    this.showActionError(event.detail);
  }
}

defineElement("parcels-week-card", ParcelsWeekCard);
registerCard("parcels-week-card", STRINGS.weekCardName, STRINGS.weekCardDescription);

declare global {
  interface HTMLElementTagNameMap {
    "parcels-week-card": ParcelsWeekCard;
  }
}
