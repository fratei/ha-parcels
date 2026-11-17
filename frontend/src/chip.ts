/** The parcel chip shared by the week and list cards. */
import { html, nothing, type TemplateResult } from "lit";
import { classMap } from "lit/directives/class-map.js";
import { styleMap } from "lit/directives/style-map.js";
import { chipMeta, describeParcel } from "./describe.ts";
import type { LocaleOptions } from "./format.ts";
import { parcelTitle } from "./labels.ts";
import type { Placement } from "./placement.ts";
import { statusColor } from "./status.ts";
import { STRINGS, fmt } from "./strings.ts";
import type { Parcel } from "./types.ts";

export interface ChipOptions {
  locale: LocaleOptions;
  placement?: Placement | null;
  continuesBefore?: boolean;
  continuesAfter?: boolean;
  /** Show the status in the meta line (the list card). */
  showStatus?: boolean;
  /** Show the dates of a span over several days (the stacked week). */
  showRange?: boolean;
  /** An Undo or Keep for this parcel is running. */
  busy?: boolean;
  /** Extra inline styles, e.g. the position in the week grid. */
  position?: Readonly<Record<string, string>>;
  onOpen: (parcel: Parcel, opener: HTMLElement) => void;
  onUndoMerge: (parcel: Parcel) => void;
  onKeepMerge: (parcel: Parcel) => void;
}

/** Selector of the main button of a parcel's chip (the first one when it shows on several days). */
export function chipSelector(parcelId: string): string {
  return `.chip[data-parcel-id="${CSS.escape(parcelId)}"] button.chip-main`;
}

function renderMergeNote(parcel: Parcel, title: string, options: ChipOptions): TemplateResult {
  const busy = options.busy ? "true" : "false";
  return html`<div class="merge-note">
    <ha-icon icon="mdi:call-merge" aria-hidden="true"></ha-icon>
    <span class="merge-label">${STRINGS.autoMerged}</span>
    <button
      type="button"
      class="link-btn"
      aria-label=${fmt(STRINGS.undoMergeLabel, { title })}
      aria-disabled=${busy}
      @click=${() => options.onUndoMerge(parcel)}
    >
      ${STRINGS.undo}
    </button>
    <button
      type="button"
      class="link-btn"
      aria-label=${fmt(STRINGS.keepMergeLabel, { title })}
      aria-disabled=${busy}
      @click=${() => options.onKeepMerge(parcel)}
    >
      ${STRINGS.keep}
    </button>
  </div>`;
}

/**
 * A parcel coloured by its status, with its name, carrier and window, the
 * "AI" badge, a lock when private and the auto-merge note. Tapping it opens the
 * details; restricted parcels (another user's private ones) aren't interactive.
 */
export function renderChip(parcel: Parcel, options: ChipOptions): TemplateResult {
  const { locale } = options;
  const placement = options.placement ?? null;
  const title = parcelTitle(parcel);
  const description = describeParcel(parcel, {
    locale,
    placement,
    continuesBefore: options.continuesBefore,
    continuesAfter: options.continuesAfter,
  });
  const meta = chipMeta(parcel, {
    locale,
    placement,
    showStatus: options.showStatus,
    showRange: options.showRange,
  });
  const classes = {
    chip: true,
    "cont-before": options.continuesBefore === true,
    "cont-after": options.continuesAfter === true,
    returned: parcel.status === "returned",
  };
  const style = { ...options.position, "--chip-color": statusColor(parcel.status) };
  // The visible parts; the accessible name is the full description instead.
  const row = html`<span class="chip-row" aria-hidden=${parcel.restricted ? "true" : nothing}>
    ${options.continuesBefore ? html`<span class="cont">‹</span>` : nothing}
    ${parcel.status === "delivered" ? html`<span class="check">✓</span>` : nothing}
    <span class="chip-text">
      <span class="chip-title">${title}</span>
      ${meta ? html`<span class="chip-meta">${meta}</span>` : nothing}
    </span>
    ${parcel.ai && !parcel.restricted ? html`<span class="badge ai">${STRINGS.aiBadge}</span>` : nothing}
    ${parcel.private || parcel.restricted
      ? html`<ha-icon class="lock" icon="mdi:lock"></ha-icon>`
      : nothing}
    ${options.continuesAfter ? html`<span class="cont">›</span>` : nothing}
  </span>`;

  if (parcel.restricted) {
    return html`<div class=${classMap(classes)} style=${styleMap(style)}>
      <div class="chip-main" title=${description}>
        <span class="sr-only">${description}</span>
        ${row}
      </div>
    </div>`;
  }
  return html`<div class=${classMap(classes)} style=${styleMap(style)} data-parcel-id=${parcel.id}>
    <button
      type="button"
      class="chip-main"
      aria-haspopup="dialog"
      aria-label=${description}
      title=${description}
      @click=${(event: MouseEvent) => options.onOpen(parcel, event.currentTarget as HTMLElement)}
    >
      ${row}
    </button>
    ${parcel.auto_merged ? renderMergeNote(parcel, title, options) : nothing}
  </div>`;
}
