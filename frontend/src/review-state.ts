/** The review card's optimistic state and its local AI line, kept apart so they can be tested. */
import { STRINGS, fmt } from "./strings.ts";

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
