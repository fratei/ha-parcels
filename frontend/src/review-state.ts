/** The review card's optimistic state and its text, kept apart so they can be tested. */
import { STRINGS, fmt } from "./strings.ts";
import type { SenderChecks, TrustResult } from "./types.ts";

/**
 * Why an item is hidden: "pending" while its command runs, then the snapshot
 * it was handled under, until a newer snapshot shows the server's lists.
 */
export type HiddenEntry<S extends object> = "pending" | S;

export type HiddenItems<S extends object> = ReadonlyMap<string, HiddenEntry<S>>;

export function isHidden<S extends object>(
  hidden: HiddenItems<S>,
  itemId: string,
  snapshot: S | null,
): boolean {
  const entry = hidden.get(itemId);
  return entry === "pending" || (entry !== undefined && entry === snapshot);
}

/** The items that aren't hidden; the same array when none is. */
export function withoutHidden<T extends { id: string }, S extends object>(
  items: readonly T[],
  hidden: HiddenItems<S>,
  snapshot: S | null,
): readonly T[] {
  if (!hidden.size) {
    return items;
  }
  const visible = items.filter((item) => !isHidden(hidden, item.id, snapshot));
  return visible.length === items.length ? items : visible;
}

/** Hides items while their command runs. */
export function hidePending<S extends object>(
  hidden: HiddenItems<S>,
  itemIds: readonly string[],
): HiddenItems<S> {
  const next = new Map(hidden);
  for (const itemId of itemIds) {
    next.set(itemId, "pending");
  }
  return next;
}

/** Shows items again, e.g. after their command failed. */
export function unhide<S extends object>(
  hidden: HiddenItems<S>,
  itemIds: readonly string[],
): HiddenItems<S> {
  const next = new Map(hidden);
  for (const itemId of itemIds) {
    next.delete(itemId);
  }
  return next;
}

/**
 * After a command succeeded: items still in the current snapshot stay hidden
 * until the next one; the others are already gone.
 */
export function hideHandled<S extends object>(
  hidden: HiddenItems<S>,
  itemIds: readonly string[],
  snapshot: S | null,
  listed: (itemId: string) => boolean,
): HiddenItems<S> {
  const next = new Map(hidden);
  for (const itemId of itemIds) {
    if (snapshot && listed(itemId)) {
      next.set(itemId, snapshot);
    } else {
      next.delete(itemId);
    }
  }
  return next;
}

/** Forgets the items handled under an older snapshot; the same map when there are none. */
export function settleHidden<S extends object>(
  hidden: HiddenItems<S>,
  snapshot: S | null,
): HiddenItems<S> {
  let next: Map<string, HiddenEntry<S>> | null = null;
  for (const [itemId, entry] of hidden) {
    if (entry !== "pending" && entry !== snapshot) {
      next ??= new Map(hidden);
      next.delete(itemId);
    }
  }
  return next ?? hidden;
}

/** "3 e-mails waiting for the local AI, about 3 min"; null when none is waiting. */
export function aiQueueText(queue: number, seconds: number | null): string | null {
  if (queue <= 0) {
    return null;
  }
  const waiting = queue === 1 ? STRINGS.aiQueueOne : fmt(STRINGS.aiQueueMany, { count: queue });
  if (seconds === null) {
    return waiting;
  }
  const minutes = Math.max(1, Math.round(seconds / 60));
  return minutes < 120
    ? fmt(STRINGS.aiQueueMinutes, { queue: waiting, minutes })
    : fmt(STRINGS.aiQueueHours, { queue: waiting, hours: Math.round(minutes / 60) });
}

function counted(count: number, one: string, many: string): string | null {
  if (count <= 0) {
    return null;
  }
  return count === 1 ? one : fmt(many, { count });
}

/** "Trusted shop.example: added 1 e-mail, reading 2 e-mails again, 1 still needs review." */
export function trustResultText(result: TrustResult): string {
  const parts = [
    counted(result.added, STRINGS.trustAddedOne, STRINGS.trustAddedMany),
    counted(result.rechecking, STRINGS.trustRecheckOne, STRINGS.trustRecheckMany),
    counted(result.kept, STRINGS.trustKeptOne, STRINGS.trustKeptMany),
  ].filter((part): part is string => part !== null);
  return parts.length
    ? fmt(STRINGS.trustDoneWith, { domain: result.domain, parts: parts.join(", ") })
    : fmt(STRINGS.trustDone, { domain: result.domain });
}

/** The rows of "Sender check details": headers, the servers that wrote them, and the results. */
export function senderCheckRows(checks: SenderChecks): Array<[string, string]> {
  const rows: Array<[string, string]> = [[STRINGS.checkHeaders, String(checks.headers)]];
  if (checks.servers.length) {
    rows.push([
      STRINGS.checkServers,
      checks.servers.map((server) => server || STRINGS.checkNoServer).join(", "),
    ]);
  }
  if (checks.originals > 0) {
    rows.push([STRINGS.checkOriginals, String(checks.originals)]);
  }
  if (checks.used === null) {
    rows.push([STRINGS.checkUsed, STRINGS.checkUsedNone]);
    return rows;
  }
  rows.push(
    [STRINGS.checkUsed, fmt(STRINGS.checkUsedHeader, { n: checks.used + 1 })],
    ["DKIM", checks.dkim || STRINGS.checkNoResult],
    ["DMARC", checks.dmarc || STRINGS.checkNoResult],
    ["SPF", checks.spf || STRINGS.checkNoResult],
  );
  return rows;
}
