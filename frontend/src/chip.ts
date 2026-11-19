/** The parcel chip shared by the week and list cards. */
import { html, nothing, type TemplateResult } from "lit";
import { classMap } from "lit/directives/class-map.js";
import { styleMap } from "lit/directives/style-map.js";
import { chipMeta, chipPin, describeParcel, itemsSummary, sellerLine } from "./describe.ts";
import type { LocaleOptions } from "./format.ts";
import { boxParcel } from "./groups.ts";
import { parcelTitle } from "./labels.ts";
import type { Placement } from "./placement.ts";
import { RETURN_COLOR, RETURN_ICON, describeReturn, isReturnDone, returnStateLine, returnTitle } from "./returns.ts";
import { statusColor } from "./status.ts";
import { STRINGS, fmt } from "./strings.ts";
import type { CustomerReturn, Parcel } from "./types.ts";

export interface ChipOptions {
  locale: LocaleOptions;
  placement?: Placement | null;
  continuesBefore?: boolean;
  continuesAfter?: boolean;
  /** Show the status in the meta line (the list card). */
  showStatus?: boolean;
  /** Show the dates of a span over several days (the stacked week). */
  showRange?: boolean;
  /** The packages of a shipment shown as one box, the parcel among them; absent when alone. */
  members?: readonly Parcel[];
  /** "Possibly: …", shown instead of "Items not known yet" when a suggestion names candidates. */
  possibly?: string | null;
  /** An Undo or Keep for this parcel (or a package in its box) is running. */
  busy?: boolean;
  /** Extra inline styles, e.g. the position in the week grid. */
  position?: Readonly<Record<string, string>>;
  onOpen: (parcel: Parcel, opener: HTMLElement) => void;
  onUndoMerge: (parcel: Parcel) => void;
  onKeepMerge: (parcel: Parcel) => void;
  onUndoInferred: (parcel: Parcel) => void;
  onKeepInferred: (parcel: Parcel) => void;
}

/**
 * Selector of the main button of the chip showing a parcel, alone or in a
 * shipment's box (the first one when it shows on several days).
 */
export function chipSelector(parcelId: string): string {
  return `.chip[data-parcels~="${CSS.escape(parcelId)}"] button.chip-main`;
}

interface NoteText {
  icon: string;
  label: string;
  /** Which package of a box the note is about (its tracking number). */
  detail: string | null;
  undoLabel: string;
  keepLabel: string;
}

/** A note under the chip about something done automatically, with Undo and Keep. */
function renderNote(
  text: NoteText,
  busy: boolean | undefined,
  onUndo: () => void,
  onKeep: () => void,
): TemplateResult {
  const disabled = busy ? "true" : "false";
  return html`<div class="merge-note">
    <ha-icon icon=${text.icon} aria-hidden="true"></ha-icon>
    <span class="merge-label"
      >${text.label}${text.detail
        ? html` <span class="merge-detail">${text.detail}</span>`
        : nothing}</span
    >
    <button
      type="button"
      class="link-btn"
      aria-label=${text.undoLabel}
      aria-disabled=${disabled}
      @click=${onUndo}
    >
      ${STRINGS.undo}
    </button>
    <button
      type="button"
      class="link-btn"
      aria-label=${text.keepLabel}
      aria-disabled=${disabled}
      @click=${onKeep}
    >
      ${STRINGS.keep}
    </button>
  </div>`;
}

/** The name a note's buttons use: the parcel's, plus the package's number in a box. */
interface NoteSubject {
  title: string;
  detail: string | null;
}

function noteSubject(parcel: Parcel, title: string, inBox: boolean): NoteSubject {
  const detail = inBox ? (parcel.tracking_number?.trim() ?? null) || null : null;
  return { title: detail ? `${title} ${detail}` : title, detail };
}

function renderMergeNote(parcel: Parcel, subject: NoteSubject, options: ChipOptions): TemplateResult {
  const { title, detail } = subject;
  return renderNote(
    {
      icon: "mdi:call-merge",
      label: STRINGS.autoMerged,
      detail,
      undoLabel: fmt(STRINGS.undoMergeLabel, { title }),
      keepLabel: fmt(STRINGS.keepMergeLabel, { title }),
    },
    options.busy,
    () => options.onUndoMerge(parcel),
    () => options.onKeepMerge(parcel),
  );
}

function renderInferredNote(
  parcel: Parcel,
  subject: NoteSubject,
  options: ChipOptions,
): TemplateResult {
  const { title, detail } = subject;
  return renderNote(
    {
      icon: "mdi:package-variant-closed-check",
      label: STRINGS.inferred,
      detail,
      undoLabel: fmt(STRINGS.undoInferredLabel, { title }),
      keepLabel: fmt(STRINGS.keepInferredLabel, { title }),
    },
    options.busy,
    () => options.onUndoInferred(parcel),
    () => options.onKeepInferred(parcel),
  );
}

/** Keeps an empty line's height, so every chip has three lines. */
const BLANK = "\u00a0";

/**
 * A parcel coloured by its status, on three lines: the seller; the carrier,
 * window and PIN; the items. Then the "AI" badge, a lock when private, a hint
 * when only the details hold a PIN and the auto-merge and inferred-delivery
 * notes. Packages of one shipment show as one
 * box with their count and a note per package. Tapping it opens the details
 * (of the box's first package); restricted parcels (another user's private
 * ones) aren't interactive.
 */
export function renderChip(first: Parcel, options: ChipOptions): TemplateResult {
  const { locale } = options;
  const placement = options.placement ?? null;
  const members = options.members && options.members.length > 1 ? options.members : [first];
  const inBox = members.length > 1;
  const parcel = boxParcel(first, members);
  const title = parcelTitle(parcel);
  const pin = chipPin(parcel);
  const items = itemsSummary(parcel);
  const possibly = items === null && !parcel.restricted ? (options.possibly ?? null) : null;
  const description = describeParcel(parcel, {
    locale,
    placement,
    count: members.length,
    continuesBefore: options.continuesBefore,
    continuesAfter: options.continuesAfter,
    possibly,
  });
  const meta = chipMeta(parcel, {
    locale,
    placement,
    count: members.length,
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
      <span class=${classMap({ "chip-title": true, unknown: !parcel.restricted && !parcel.merchant?.trim() })}
        >${sellerLine(parcel)}</span
      >
      <span class="chip-line">
        <span class="chip-meta">${meta || BLANK}</span>
        ${pin ? html`<span class="chip-pin">${pin}</span>` : nothing}
      </span>
      <span
        class=${classMap({
          "chip-items": true,
          unknown: items === null && possibly === null && !parcel.restricted,
          possibly: possibly !== null,
        })}
        >${items ?? possibly ?? (parcel.restricted ? BLANK : STRINGS.itemsNotKnown)}</span
      >
    </span>
    ${(parcel.ai || parcel.ai_filled) && !parcel.restricted
      ? html`<span class="badge ai">${STRINGS.aiBadge}</span>`
      : nothing}
    ${parcel.has_code && !pin && !parcel.restricted
      ? html`<ha-icon class="lock" icon="mdi:dialpad" title=${STRINGS.hasCode}></ha-icon>`
      : nothing}
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
  return html`<div
    class=${classMap(classes)}
    style=${styleMap(style)}
    data-parcel-id=${parcel.id}
    data-parcels=${members.map((member) => member.id).join(" ")}
  >
    <button
      type="button"
      class="chip-main"
      aria-haspopup="dialog"
      aria-label=${description}
      title=${description}
      @click=${(event: MouseEvent) => options.onOpen(first, event.currentTarget as HTMLElement)}
    >
      ${row}
    </button>
    ${members.map((member) => {
      const subject = noteSubject(member, title, inBox);
      return html`${member.auto_merged ? renderMergeNote(member, subject, options) : nothing}${member.inferred
        ? renderInferredNote(member, subject, options)
        : nothing}`;
    })}
  </div>`;
}

export interface ReturnChipOptions {
  locale: LocaleOptions;
  /** Today in the home's time zone, "YYYY-MM-DD": a pickup day before it is over. */
  today: string;
  /** Extra inline styles, e.g. the position in the week grid. */
  position?: Readonly<Record<string, string>>;
  onOpen: (ret: CustomerReturn, opener: HTMLElement) => void;
}

/** Selector of the main button of a return's chip. */
export function returnChipSelector(returnId: string): string {
  return `.chip[data-return-id="${CSS.escape(returnId)}"] button.chip-main`;
}

/**
 * A customer return on its pickup day, in the returns colour with a
 * parcel-going-out icon: the
 * shop; how far it is ("Return pickup", "Return picked up"…) and the carrier;
 * the items. A lock when private. Tapping it opens the return's details;
 * someone else's private return isn't interactive.
 */
export function renderReturnChip(ret: CustomerReturn, options: ReturnChipOptions): TemplateResult {
  const description = describeReturn(ret, options.locale, options.today);
  const items = itemsSummary(ret);
  const classes = { chip: true, return: true, done: isReturnDone(ret, options.today) };
  const style = { ...options.position, "--chip-color": RETURN_COLOR };
  const row = html`<span class="chip-row" aria-hidden=${ret.restricted ? "true" : nothing}>
    <ha-icon class="ret-icon" icon=${RETURN_ICON}></ha-icon>
    <span class="chip-text">
      <span class="chip-title">${returnTitle(ret)}</span>
      <span class="chip-line">
        <span class="chip-meta">${returnStateLine(ret, options.today)}</span>
      </span>
      <span class="chip-items">${items ?? BLANK}</span>
    </span>
    ${ret.private || ret.restricted ? html`<ha-icon class="lock" icon="mdi:lock"></ha-icon>` : nothing}
  </span>`;

  if (ret.restricted) {
    return html`<div class=${classMap(classes)} style=${styleMap(style)}>
      <div class="chip-main" title=${description}>
        <span class="sr-only">${description}</span>
        ${row}
      </div>
    </div>`;
  }
  return html`<div class=${classMap(classes)} style=${styleMap(style)} data-return-id=${ret.id}>
    <button
      type="button"
      class="chip-main"
      aria-haspopup="dialog"
      aria-label=${description}
      title=${description}
      @click=${(event: MouseEvent) => options.onOpen(ret, event.currentTarget as HTMLElement)}
    >
      ${row}
    </button>
  </div>`;
}
