/**
 * Customer returns: items sent back to a shop. They show on their pickup day
 * in their own colour, with a parcel-going-out icon and the words "Return
 * pickup", apart from the deliveries; the parcel they came in keeps its own
 * day.
 */
import { compareYmd } from "./dates.ts";
import { itemsSummary } from "./describe.ts";
import { formatDate, formatDayTime, type LocaleOptions } from "./format.ts";
import { carrierLabel } from "./labels.ts";
import { STRINGS, fmt } from "./strings.ts";
import type { CustomerReturn, PickupRule } from "./types.ts";

/** A colour no parcel status uses: returns go out, deliveries come in. */
export const RETURN_COLOR = "var(--pink-color, #e91e63)";

/** Shown before a return's title, on its chip and its badges: a parcel going out. */
export const RETURN_ICON = "mdi:package-up";

const RULE_TEXT: Readonly<Record<PickupRule, string>> = {
  email: STRINGS.pickupRuleEmail,
  next_working_day: STRINGS.pickupRuleNextWorkingDay,
  assumed: STRINGS.pickupRuleAssumed,
};

function clean(value: string | null): string | null {
  const text = value?.replace(/\s+/g, " ").trim();
  return text ? text : null;
}

/**
 * Done once someone marks it picked up or its pickup day is over, or when the
 * shop says it has the items.
 */
export function isReturnDone(
  ret: Pick<CustomerReturn, "day" | "received" | "picked_up">,
  today: string,
): boolean {
  return ret.received || ret.picked_up !== null || compareYmd(ret.day, today) < 0;
}

/** "Mark picked up" is offered until the return is done, when a carrier comes for it. */
export function canMarkPickedUp(ret: CustomerReturn, today: string): boolean {
  return !ret.restricted && ret.pickup !== null && !isReturnDone(ret, today);
}

/** Its Undo, until the pickup day is over: then it's done anyway. */
export function canUndoPickedUp(ret: CustomerReturn, today: string): boolean {
  return !ret.restricted && ret.picked_up !== null && !ret.received && compareYmd(ret.day, today) >= 0;
}

/** The shop; "Private return" for someone else's private one. */
export function returnTitle(ret: CustomerReturn): string {
  if (ret.restricted) {
    return STRINGS.privateReturn;
  }
  return clean(ret.merchant) ?? STRINGS.unknownSeller;
}

/** Where the pickup day comes from; null without one. */
export function pickupRuleText(rule: PickupRule | null): string | null {
  return rule ? RULE_TEXT[rule] : null;
}

function returnCarrier(ret: CustomerReturn): string | null {
  return ret.restricted ? null : carrierLabel(ret);
}

/** How far the return is: "Return pickup", "Return picked up"… */
export function returnState(ret: CustomerReturn, today: string): string {
  if (ret.received) {
    return STRINGS.returnReceived;
  }
  if (ret.picked_up !== null) {
    return STRINGS.returnPickedUp;
  }
  if (ret.pickup === null) {
    return STRINGS.returnStarted;
  }
  return isReturnDone(ret, today) ? STRINGS.returnPickedUp : STRINGS.returnPickup;
}

/** The chip's second line: how far the return is, and the carrier when known. */
export function returnStateLine(ret: CustomerReturn, today: string): string {
  const state = returnState(ret, today);
  const carrier = returnCarrier(ret);
  return carrier ? `${state} · ${carrier}` : state;
}

/**
 * Everything a return's chip shows, as one sentence for screen readers and
 * the tooltip, e.g. "Return to Example Shop, pickup Thu 16 Jul, usually the
 * working day after the e-mail, carrier UPS, Blue mug".
 */
export function describeReturn(ret: CustomerReturn, locale: LocaleOptions, today: string): string {
  const merchant = ret.restricted ? null : clean(ret.merchant);
  const parts: string[] = [
    ret.restricted
      ? STRINGS.privateReturn
      : merchant
        ? fmt(STRINGS.returnTo, { merchant })
        : STRINGS.returnPlain,
  ];
  const date = formatDate(ret.day, locale);
  const marked = ret.picked_up === null ? "" : formatDayTime(ret.picked_up, locale);
  if (marked) {
    parts.push(fmt(STRINGS.pickedUpOn, { date: marked }));
  } else if (ret.pickup === null) {
    parts.push(fmt(STRINGS.returnStartedOn, { date }));
  } else if (!isReturnDone(ret, today)) {
    parts.push(fmt(STRINGS.pickupOn, { date }));
    const rule = pickupRuleText(ret.pickup_rule);
    if (rule) {
      parts.push(rule);
    }
  } else if (compareYmd(ret.day, today) <= 0) {
    // A shop that has the items before the expected day shows that day was wrong.
    parts.push(fmt(STRINGS.pickedUpOn, { date }));
  }
  if (ret.received) {
    parts.push(STRINGS.receivedByShopLabel);
  }
  const carrier = returnCarrier(ret);
  if (carrier) {
    parts.push(fmt(STRINGS.carrierIs, { carrier }));
  }
  const items = itemsSummary(ret);
  if (items) {
    parts.push(items);
  }
  if (ret.private || ret.restricted) {
    parts.push(STRINGS.privateLabel);
  }
  return parts.join(", ");
}

/** The returns of items that came in a parcel. */
export function returnsOfParcel(
  returns: readonly CustomerReturn[],
  parcelId: string,
): CustomerReturn[] {
  return returns.filter((ret) => ret.parcel_ids.includes(parcelId));
}
